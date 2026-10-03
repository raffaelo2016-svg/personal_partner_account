from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.files import _has_valid_signature
from app.config import settings
from app.integrations.bitrix24.documents import (
    CRM_ACTIVITY_ENTITY_TYPE,
    FILE_ENTITY_TYPE,
    TIMELINE_COMMENT_ENTITY_TYPE,
    FileFolderContext,
    build_file_operation_payload,
    client_folder_name,
    disk_file_marker,
    disk_file_name,
    execute_file_creation,
    extract_crm_activity_event_reference,
    extract_timeline_comment_event_reference,
    file_marker,
    import_initial_documents_from_folder,
    load_file_folder_context,
    partner_folder_name,
    process_crm_activity_add_event,
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


def _folder_context() -> FileFolderContext:
    return FileFolderContext(
        partner_root_folder_id="300",
        partner_folder_name="Самсонюк Евгений Вячеславович",
        client_folder_name="Иванов Иван Иванович",
        remote_file_name="паспорт [test].pdf",
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

    result = await execute_file_creation(remote, operation, folder_context=_folder_context())

    assert result == "90:700"
    remote.list_all.assert_awaited_once()
    remote.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_timeline_disk_marker_prevents_duplicate_upload():
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
    remote.list_all.return_value = [{"ID": "90", "COMMENT": f"{marker}\n{disk_file_marker('700')}", "FILES": []}]

    result = await execute_file_creation(remote, operation, folder_context=_folder_context())

    assert result == "90:700"
    remote.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_document_is_uploaded_to_partner_client_documents_folder():
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
    remote.client_endpoint = "https://bitrix.uriteh.ru/rest/"
    remote.list_all.side_effect = [[], [], [], []]
    remote.call.side_effect = [
        {"ID": "500", "TYPE": "folder", "NAME": _folder_context().client_folder_name},
        {"ID": "600", "TYPE": "folder", "NAME": "Первоначальные документы"},
        {
            "ID": "700",
            "TYPE": "file",
            "NAME": _folder_context().remote_file_name,
            "DETAIL_URL": "https://bitrix.uriteh.ru/company/personal/user/1/disk/file/700/",
        },
        "90",
    ]

    with patch("app.integrations.bitrix24.documents.download_file_async", new=AsyncMock(return_value=b"%PDF-1.7")):
        result = await execute_file_creation(remote, operation, folder_context=_folder_context())

    assert result == "90:700"
    client_folder_call = remote.call.await_args_list[0]
    assert client_folder_call.args == (
        "disk.folder.addsubfolder",
        {"id": "300", "data": {"NAME": _folder_context().client_folder_name}},
    )
    documents_folder_call = remote.call.await_args_list[1]
    assert documents_folder_call.args == (
        "disk.folder.addsubfolder",
        {"id": "500", "data": {"NAME": "Первоначальные документы"}},
    )
    upload_method, upload_payload = remote.call.await_args_list[2].args
    assert upload_method == "disk.folder.uploadfile"
    assert upload_payload["id"] == "600"
    assert upload_payload["data"]["NAME"] == _folder_context().remote_file_name
    assert record.original_name not in str(upload_payload)
    timeline_method, timeline_payload = remote.call.await_args_list[3].args
    assert timeline_method == "crm.timeline.comment.add"
    assert "FILES" not in timeline_payload["fields"]
    assert disk_file_marker("700") in timeline_payload["fields"]["COMMENT"]
    assert "https://bitrix.uriteh.ru/" in timeline_payload["fields"]["COMMENT"]


@pytest.mark.asyncio
async def test_existing_folder_tree_and_file_are_reused():
    record = _record()
    remote_name = _folder_context().remote_file_name
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"file:create:{record.id}:v1",
        local_entity_type=FILE_ENTITY_TYPE,
        local_entity_id=record.id,
        bitrix_method="crm.timeline.comment.add",
        payload=build_file_operation_payload(record, deal_id="456"),
    )
    remote = AsyncMock()
    remote.client_endpoint = "https://bitrix.uriteh.ru/rest/"
    remote.list_all.side_effect = [
        [],
        [{"ID": "500", "TYPE": "folder", "NAME": _folder_context().client_folder_name}],
        [{"ID": "600", "TYPE": "folder", "NAME": "Первоначальные документы"}],
        [
            {
                "ID": "700",
                "TYPE": "file",
                "NAME": remote_name,
                "DETAIL_URL": "/company/personal/user/1/disk/file/700/",
            }
        ],
    ]
    remote.call.return_value = "90"

    with patch("app.integrations.bitrix24.documents.download_file_async", new=AsyncMock(return_value=b"%PDF-1.7")):
        result = await execute_file_creation(remote, operation, folder_context=_folder_context())

    assert result == "90:700"
    remote.call.assert_awaited_once()
    assert remote.call.await_args.args[0] == "crm.timeline.comment.add"
    assert "https://bitrix.uriteh.ru/company/" in remote.call.await_args.args[1]["fields"]["COMMENT"]


@pytest.mark.asyncio
async def test_missing_partner_and_nested_folders_are_created_on_first_upload():
    record = _record()
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"file:create:{record.id}:v1",
        local_entity_type=FILE_ENTITY_TYPE,
        local_entity_id=record.id,
        bitrix_method="crm.timeline.comment.add",
        payload=build_file_operation_payload(record, deal_id="456"),
    )
    context = FileFolderContext(
        partner_root_folder_id=None,
        partner_folder_name="Самсонюк Евгений Вячеславович",
        client_folder_name="Иванов Иван Иванович",
        remote_file_name="паспорт [test].pdf",
    )
    remote = AsyncMock()
    remote.client_endpoint = "https://bitrix.uriteh.ru/rest/"
    remote.list_all.side_effect = [
        [],
        [{"ID": "10", "NAME": "Общий диск"}],
        [{"ID": "20", "TYPE": "folder", "NAME": "ПАРТНЕРЫ"}],
        [],
        [],
        [],
        [],
    ]
    remote.call.side_effect = [
        {"ID": "300", "TYPE": "folder", "NAME": context.partner_folder_name},
        {"ID": "500", "TYPE": "folder", "NAME": context.client_folder_name},
        {"ID": "600", "TYPE": "folder", "NAME": "Первоначальные документы"},
        {
            "ID": "700",
            "TYPE": "file",
            "NAME": context.remote_file_name,
            "DETAIL_URL": "https://bitrix.uriteh.ru/company/personal/user/1/disk/file/700/",
        },
        "90",
    ]

    with patch("app.integrations.bitrix24.documents.download_file_async", new=AsyncMock(return_value=b"%PDF-1.7")):
        result = await execute_file_creation(remote, operation, folder_context=context)

    assert result == "90:700"
    assert remote.list_all.await_args_list[1].args == (
        "disk.storage.getlist",
        {"filter": {"ENTITY_TYPE": "common"}},
    )
    assert remote.list_all.await_args_list[1].kwargs == {"max_pages": 5}
    assert remote.call.await_args_list[0].args == (
        "disk.folder.addsubfolder",
        {"id": "20", "data": {"NAME": "Самсонюк Евгений Вячеславович"}},
    )
    assert remote.call.await_args_list[1].args == (
        "disk.folder.addsubfolder",
        {"id": "300", "data": {"NAME": "Иванов Иван Иванович"}},
    )
    assert remote.call.await_args_list[2].args == (
        "disk.folder.addsubfolder",
        {"id": "500", "data": {"NAME": "Первоначальные документы"}},
    )


@pytest.mark.asyncio
async def test_all_partners_use_shared_document_folder_flow():
    record = _record()
    client = Client(
        id=record.client_id,
        partner_id=uuid4(),
        type="before_court",
        full_name="Петров Пётр Петрович",
        bitrix_deal_id="456",
    )
    partner = Partner(
        id=client.partner_id,
        user_id=uuid4(),
        company_name="ООО Другой партнёр",
        director_name="Петров Пётр Петрович",
        inn="7701234567",
        phone="+79990000002",
    )
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"file:create:{record.id}:v1",
        local_entity_type=FILE_ENTITY_TYPE,
        local_entity_id=record.id,
        bitrix_method="crm.timeline.comment.add",
        payload=build_file_operation_payload(record, deal_id="456"),
    )
    db = AsyncMock()
    db.get.side_effect = [record, client, partner]
    partner_rows = Mock()
    partner_rows.all.return_value = [(partner.id, partner.company_name)]
    db.execute.return_value = partner_rows

    context = await load_file_folder_context(db, operation)

    assert context.partner_root_folder_id is None
    assert context.partner_folder_name == "ООО Другой партнёр"
    assert context.client_folder_name == "Петров Пётр Петрович"
    assert context.remote_file_name == disk_file_name(record)


def test_client_folder_name_is_readable_and_safe():
    client = Client(
        id=uuid4(),
        partner_id=uuid4(),
        type="before_court",
        full_name='Иванов / Иван: "Тест"',
        bitrix_deal_id="456",
    )

    result = client_folder_name(client)

    assert result == "Иванов - Иван- -Тест-"


def test_disk_file_name_keeps_original_name_and_stable_id_suffix():
    record = _record()

    result = disk_file_name(record)

    assert result == f"personal-name [{record.id.hex[:8]}].pdf"


def test_partner_folder_name_uses_cabinet_name_and_sanitizes_it():
    partner = Partner(
        id=uuid4(),
        user_id=uuid4(),
        company_name='ООО "Право / Партнёры"',
        director_name="Самсонюк Евгений Вячеславович",
        inn="123456789012",
        phone="+79990000001",
    )

    assert partner_folder_name(partner) == "ООО -Право - Партнёры-"


@pytest.mark.asyncio
async def test_duplicate_partner_folder_name_gets_stable_identifier():
    record = _record()
    client = Client(
        id=record.client_id,
        partner_id=uuid4(),
        type="before_court",
        full_name="Клиент Один",
        bitrix_deal_id="456",
    )
    partner = Partner(
        id=client.partner_id,
        user_id=uuid4(),
        company_name="Одинаковое имя",
        director_name="Партнёр Второй",
        inn="123456789012",
        phone="+79990000001",
    )
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"file:create:{record.id}:v1",
        local_entity_type=FILE_ENTITY_TYPE,
        local_entity_id=record.id,
        bitrix_method="crm.timeline.comment.add",
        payload=build_file_operation_payload(record, deal_id="456"),
    )
    db = AsyncMock()
    db.get.side_effect = [record, client, partner]
    partner_rows = Mock()
    partner_rows.all.return_value = [(uuid4(), "Одинаковое имя"), (partner.id, "Одинаковое имя")]
    db.execute.return_value = partner_rows

    context = await load_file_folder_context(db, operation)

    assert context.partner_folder_name == f"Одинаковое имя [{str(partner.id).split('-')[0]}]"


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


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"FIELDS": {"ID": "43"}}},
        {"data[FIELDS][ID]": "43"},
    ],
)
def test_crm_activity_event_reference_supports_json_and_form(payload):
    assert extract_crm_activity_event_reference("ONCRMACTIVITYADD", payload) == "43"
    assert extract_crm_activity_event_reference("ONCRMDEALADD", payload) is None


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
    with (
        patch("app.integrations.bitrix24.documents._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.documents.Bitrix24Client", return_value=context),
    ):
        completed_again = await process_timeline_comment_add_event(db_session, receipt)
    records = list((await db_session.scalars(select(FileUpload).where(FileUpload.client_id == client.id))).all())
    assert completed_again is True
    assert len(records) == 1


@pytest.mark.asyncio
async def test_file_placed_directly_in_initial_documents_folder_is_imported_once(db_session: AsyncSession):
    client = await _saved_client(db_session)
    folder_tree = [
        [{"ID": "10", "NAME": "Общий диск"}],
        [{"ID": "20", "TYPE": "folder", "NAME": "ПАРТНЕРЫ"}],
        [{"ID": "30", "TYPE": "folder", "NAME": "ООО Документы"}],
        [{"ID": "40", "TYPE": "folder", "NAME": "Иванов Иван Иванович"}],
        [{"ID": "50", "TYPE": "folder", "NAME": "Первоначальные документы"}],
        [{"ID": "702", "TYPE": "file", "NAME": "заявление.pdf", "SIZE": "8"}],
    ]
    remote = AsyncMock()
    remote.list_all.side_effect = folder_tree + folder_tree
    remote.call.return_value = {
        "ID": "702",
        "NAME": "заявление.pdf",
        "SIZE": "8",
        "DOWNLOAD_URL": f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/download.json?token=signed",
    }
    remote.download_file.return_value = b"%PDF-1.7"

    with patch(
        "app.integrations.bitrix24.documents.upload_file_async",
        new=AsyncMock(return_value="uploads/folder-import.pdf"),
    ):
        imported = await import_initial_documents_from_folder(
            db_session,
            remote,
            local_client=client,
            member_id="member-doc-reverse",
        )
        imported_again = await import_initial_documents_from_folder(
            db_session,
            remote,
            local_client=client,
            member_id="member-doc-reverse",
        )

    record = await db_session.scalar(
        select(FileUpload).where(FileUpload.client_id == client.id, FileUpload.bitrix_disk_file_id == "702")
    )
    assert imported == 1
    assert imported_again == 0
    assert record is not None
    assert record.original_name == "заявление.pdf"
    assert record.bitrix_sync_status == "synced"
    assert record.bitrix_activity_id is None
    assert record.bitrix_timeline_comment_id is None
    remote.download_file.assert_awaited_once()


@pytest.mark.asyncio
async def test_external_activity_file_is_imported_to_client_once(db_session: AsyncSession):
    client = await _saved_client(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-doc-reverse",
        event_key=uuid4().hex,
        event_name="ONCRMACTIVITYADD",
        payload_hash=uuid4().hex,
        remote_entity_type=CRM_ACTIVITY_ENTITY_TYPE,
        remote_entity_id="91",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.side_effect = [
        {
            "ID": "91",
            "OWNER_TYPE_ID": "2",
            "OWNER_ID": "456",
            "DESCRIPTION": "Документ от сотрудника",
            "STORAGE_ELEMENT_IDS": [701],
        },
        {
            "ID": "701",
            "NAME": "заявление.pdf",
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
            new=AsyncMock(return_value="uploads/imported-activity.pdf"),
        ),
    ):
        completed = await process_crm_activity_add_event(db_session, receipt)

    record = await db_session.scalar(select(FileUpload).where(FileUpload.client_id == client.id))
    assert completed is True
    assert receipt.status == "completed"
    assert record is not None
    assert record.original_name == "заявление.pdf"
    assert record.bitrix_activity_id == "91"
    assert record.bitrix_timeline_comment_id is None
    assert record.bitrix_disk_file_id == "701"

    remote.call.side_effect = None
    remote.call.return_value = {
        "ID": "91",
        "OWNER_TYPE_ID": "2",
        "OWNER_ID": "456",
        "STORAGE_ELEMENT_IDS": [701],
    }
    receipt.status = "received"
    with (
        patch("app.integrations.bitrix24.documents._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.documents.Bitrix24Client", return_value=context),
    ):
        completed_again = await process_crm_activity_add_event(db_session, receipt)
    records = list((await db_session.scalars(select(FileUpload).where(FileUpload.client_id == client.id))).all())
    assert completed_again is True
    assert len(records) == 1
