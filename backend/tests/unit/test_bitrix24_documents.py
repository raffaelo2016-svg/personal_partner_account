from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.api.files import _has_valid_signature
from app.integrations.bitrix24.documents import (
    FILE_ENTITY_TYPE,
    build_file_operation_payload,
    execute_file_creation,
    file_marker,
)
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.file_upload import FileUpload


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
    remote.list_all.return_value = [{"ID": "90", "COMMENT": marker, "FILES": [{"id": "700"}]}]

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
