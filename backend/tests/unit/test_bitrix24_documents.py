from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.files import _has_valid_signature
from app.config import settings
from app.integrations.bitrix24.documents import (
    FILE_ENTITY_TYPE,
    TIMELINE_COMMENT_ENTITY_TYPE,
    build_file_operation_payload,
    execute_file_creation,
    extract_timeline_comment_event_reference,
    file_marker,
    process_timeline_comment_add_event,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.models.user import User


def _record() -> FileUpload:
    return FileUpload(
        id=uuid4(),
        client_id=uuid4(),
        document_type="passport",
        original_name="personal-name.pdf",
        s3_key=f"uploads/{uuid4()}.pdf",
        size=12,
        mime_type="application/pdf",
    )


def test_file_payload_uses_pii_free_remote_name_and_marker():
    record = _record()

    payload = build_file_operation_payload(record, deal_id="456")

    assert payload["deal_id"] == "456"
    assert payload["remote_name"] == f"document_{record.id}.pdf"
    assert record.original_name not in str(payload)
    assert payload["marker"] == file_marker(record.id)


@pytest.mark.parametrize(
    ("extension", "content"),
    [
        (".pdf", b"%PDF-1.7"),
        (".jpg", b"\xff\xd8\xffmore"),
        (".png", b"\x89PNG\r\n\x1a\nmore"),
        (".doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1more"),
        (".docx", b"PK\x03\x04more"),
    ],
)
def test_supported_file_signatures(extension: str, content: bytes):
    assert _has_valid_signature(content, extension) is True
    assert _has_valid_signature(b"not-a-document", extension) is False


@pytest.mark.asyncio
async def test_existing_timeline_marker_prevents_duplicate_upload():
    record = _record()
    marker = file_marker(record.id)
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"file:create:{record.id}:v1",
        local_entity_type=FILE_ENTITY_TYPE,
        local_entity_id=record.id,
        bitrix_method="crm.timeline.comment.add",
        payload={"deal_id": "456", "s3_key": record.s3_key, "remote_name": "document.pdf", "marker": marker},
    )
    remote = AsyncMock()
    remote.list_all.return_value = [{"ID": "90", "COMMENT": marker, "FILES": {"1": {"id": "700"}}}]

    result = await execute_file_creation(remote, operation)

    assert result == "90:700"
    remote.list_all.assert_awaited_once()
    remote.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_document_is_uploaded_without_original_filename():
    record = _record()
    payload = build_file_operation_payload(record, deal_id="456")
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"file:create:{record.id}:v1",
        local_entity_type=FILE_ENTITY_TYPE,
        local_entity_id=record.id,
        bitrix_method="crm.timeline.comment.add",
        payload=payload,
    )
    remote = AsyncMock()
    remote.list_all.return_value = []
    remote.call.side_effect = ["90", {"ID": "90", "FILES": [{"ID": "700"}]}]

    with patch("app.integrations.bitrix24.documents.download_file_async", new=AsyncMock(return_value=b"%PDF-1.7")):
        result = await execute_file_creation(remote, operation)

    assert result == "90:700"
    add_payload = remote.call.await_args_list[0].args[1]
    assert record.original_name not in str(add_payload)
    assert add_payload["fields"]["FILES"][0][0] == f"document_{record.id}.pdf"


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"ID": "42"}},
        {"data[ID]": "42"},
    ],
)
def test_timeline_comment_event_reference_supports_json_and_form(payload):
    assert extract_timeline_comment_event_reference("ONCRMTIMELINECOMMENTADD", payload) == "42"
    assert extract_timeline_comment_event_reference("ONCRMDEALADD", payload) is None


async def _saved_client(db: AsyncSession) -> Client:
    installation = BitrixInstallation(
        member_id="member-doc-reverse",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"encrypted-access",
        refresh_token_encrypted=b"encrypted-refresh",
        status="L",
    )
    user = User(email="document-reverse@example.test", hashed_password="hash", role="partner", is_active=True)
    db.add_all([installation, user])
    await db.flush()
    partner = Partner(
        user_id=user.id,
        partner_type="legal",
        company_name="ООО Документы",
        director_name="Петров Пётр Петрович",
        inn="7701234567",
        phone="+79990000001",
        status="active",
    )
    db.add(partner)
    await db.flush()
    client = Client(
        partner_id=partner.id,
        type="before_court",
        status="documents_collection",
        full_name="Иванов Иван Иванович",
        bitrix_deal_id="456",
        bitrix_sync_status="synced",
    )
    db.add(client)
    await db.flush()
    db.add(
        BitrixEntityMap(
            member_id=installation.member_id,
            local_entity_type="client_deal",
            local_entity_id=client.id,
            bitrix_entity_type="crm_deal",
            bitrix_entity_id="456",
        )
    )
    await db.flush()
    return client


@pytest.mark.asyncio
async def test_external_timeline_file_is_imported_to_client_once(db_session: AsyncSession):
    client = await _saved_client(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-doc-reverse",
        event_key=uuid4().hex,
        event_name="ONCRMTIMELINECOMMENTADD",
        payload_hash=uuid4().hex,
        remote_entity_type=TIMELINE_COMMENT_ENTITY_TYPE,
        remote_entity_id="90",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.side_effect = [
        {
            "ID": "90",
            "ENTITY_TYPE": "deal",
            "ENTITY_ID": "456",
            "COMMENT": "Документ от сотрудника",
            "FILES": {"700": {"id": 700, "name": "договор.pdf", "size": 8}},
        },
        {
            "ID": "700",
            "NAME": "договор.pdf",
            "SIZE": "8",
            "DOWNLOAD_URL": f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/download.json?token=signed",
        },
    ]
    remote.download_file.return_value = b"%PDF-1.7"
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.documents._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.documents.Bitrix24Client", return_value=context),
        patch(
            "app.integrations.bitrix24.documents.upload_file_async",
            new=AsyncMock(return_value="uploads/imported.pdf"),
        ),
    ):
        completed = await process_timeline_comment_add_event(db_session, receipt)

    record = await db_session.scalar(select(FileUpload).where(FileUpload.client_id == client.id))
    assert completed is True
    assert receipt.status == "completed"
    assert record is not None
    assert record.original_name == "договор.pdf"
    assert record.document_type == "other"
    assert record.bitrix_timeline_comment_id == "90"
    assert record.bitrix_disk_file_id == "700"
    assert record.bitrix_sync_status == "synced"
    remote.download_file.assert_awaited_once()

    remote.call.side_effect = None
    remote.call.return_value = {
        "ID": "90",
        "ENTITY_TYPE": "deal",
        "ENTITY_ID": "456",
        "COMMENT": "Документ от сотрудника",
        "FILES": {"700": {"id": 700, "name": "договор.pdf", "size": 8}},
    }
    receipt.status = "received"
    completed_again = await process_timeline_comment_add_event(db_session, receipt)
    records = list((await db_session.scalars(select(FileUpload).where(FileUpload.client_id == client.id))).all())
    assert completed_again is True
    assert len(records) == 1
