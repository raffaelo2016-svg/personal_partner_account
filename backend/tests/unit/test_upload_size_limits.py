import inspect
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers, UploadFile

from app.validation import files as file_policy


@pytest.fixture
def setup_db():
    """These unit tests use storage/database mocks and need no PostgreSQL."""


@pytest.fixture
def small_limits(monkeypatch):
    # Exercise real reads and boundary bytes without allocating 100 MiB per case.
    # The production values are checked separately below.
    monkeypatch.setattr(file_policy, "MAX_FILE_SIZE_BYTES", 16)
    monkeypatch.setattr(file_policy, "MAX_ZIP_FILE_SIZE_BYTES", 160)


def _content(filename, size):
    signature = b"PK\x03\x04" if filename.lower().endswith(".zip") else b"%PDF-"
    return signature + bytes(size - len(signature))


def _upload(filename, content):
    upload = UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": file_policy.mime_type_for_filename(filename)}),
    )
    upload.read = AsyncMock(wraps=upload.read)
    return upload


def test_production_upload_limits_are_100_mib_for_zip_and_10_mib_otherwise():
    assert file_policy.MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024
    assert file_policy.MAX_ZIP_FILE_SIZE_BYTES == 100 * 1024 * 1024
    for filename in ("documents.zip", "Documents.ZIP", r"C:\documents\Archive.ZiP"):
        assert file_policy.max_file_size_for_filename(filename) == 100 * 1024 * 1024
    for filename in ("document.pdf", "document.docx", "recording.mp3", "archive.zip.pdf", "archive.zip.exe"):
        assert file_policy.max_file_size_for_filename(filename) == 10 * 1024 * 1024


@pytest.mark.asyncio
@pytest.mark.parametrize(("filename", "size"), [("documents.zip", 17), ("Documents.ZIP", 160)])
async def test_chat_accepts_zip_above_old_limit_and_at_new_limit(monkeypatch, small_limits, filename, size):
    from app.services import chat_service

    content = _content(filename, size)
    file = _upload(filename, content)
    upload = AsyncMock(return_value="uploads/documents.zip")
    monkeypatch.setattr(chat_service, "upload_file_async", upload)

    result = await chat_service.upload_chat_file(file)

    assert result == ("uploads/documents.zip", filename, size, "application/zip")
    file.read.assert_awaited_once_with(161)
    upload.assert_awaited_once_with(content, filename, "application/zip")


@pytest.mark.asyncio
@pytest.mark.parametrize(("filename", "size", "limit"), [("documents.zip", 161, 160), ("document.pdf", 17, 16)])
async def test_chat_rejects_oversized_files_before_storage(monkeypatch, small_limits, filename, size, limit):
    from app.core.exceptions import FileTooLarge
    from app.services import chat_service

    file = _upload(filename, _content(filename, size))
    upload = AsyncMock()
    monkeypatch.setattr(chat_service, "upload_file_async", upload)

    with pytest.raises(FileTooLarge):
        await chat_service.upload_chat_file(file)

    file.read.assert_awaited_once_with(limit + 1)
    upload.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("filename", "size"), [("documents.zip", 17), ("Documents.ZIP", 160), ("document.pdf", 16)])
async def test_document_endpoint_accepts_file_at_its_format_limit(monkeypatch, small_limits, filename, size):
    from app.api import files as files_api

    content = _content(filename, size)
    file = _upload(filename, content)
    upload = AsyncMock(return_value="uploads/document")
    db = SimpleNamespace(scalar=AsyncMock(return_value=None), add=Mock(), flush=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(files_api, "_check_client_access", AsyncMock())
    monkeypatch.setattr(files_api, "upload_file_async", upload)
    monkeypatch.setattr(files_api, "schedule_file_creation", AsyncMock())
    monkeypatch.setattr(files_api, "get_presigned_url_async", AsyncMock(return_value="https://files.test/document"))
    response = Mock(return_value="serialized response")
    monkeypatch.setattr(files_api, "_read_response", response)

    result = await inspect.unwrap(files_api.upload_endpoint)(
        request=Request({"type": "http"}),
        file=file,
        client_id=str(uuid4()),
        document_type="other",
        db=db,
        current_user=SimpleNamespace(role="admin"),
    )

    assert result == "serialized response"
    limit = file_policy.max_file_size_for_filename(filename)
    file.read.assert_awaited_once_with(limit + 1)
    upload.assert_awaited_once_with(content, filename, file_policy.mime_type_for_filename(filename))
    db.commit.assert_awaited_once()
    saved_record = response.call_args.args[0]
    assert saved_record.original_name == filename
    assert saved_record.size == size


@pytest.mark.asyncio
@pytest.mark.parametrize(("filename", "size", "limit"), [("documents.zip", 161, 160), ("document.pdf", 17, 16)])
async def test_document_endpoint_rejects_oversized_file_with_bounded_read(
    monkeypatch, small_limits, filename, size, limit
):
    from app.api import files as files_api

    # Additional trailing data must remain unread once the overflow byte is found.
    file = _upload(filename, _content(filename, size + 1024))
    upload = AsyncMock()
    db = SimpleNamespace(scalar=AsyncMock(), add=Mock(), commit=AsyncMock())
    monkeypatch.setattr(files_api, "_check_client_access", AsyncMock())
    monkeypatch.setattr(files_api, "upload_file_async", upload)

    with pytest.raises(HTTPException) as error:
        await inspect.unwrap(files_api.upload_endpoint)(
            request=Request({"type": "http"}),
            file=file,
            client_id=str(uuid4()),
            db=db,
            current_user=SimpleNamespace(role="admin"),
        )

    assert error.value.status_code == 413
    assert error.value.detail["code"] == "FILE_TOO_LARGE"
    file.read.assert_awaited_once_with(limit + 1)
    assert file.file.tell() == limit + 1
    upload.assert_not_awaited()
    db.scalar.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "size", "limit"), [("documents.zip", 17, 160), ("Documents.ZIP", 160, 160), ("document.pdf", 16, 16)]
)
async def test_bitrix_import_passes_format_limit_to_bounded_download(monkeypatch, small_limits, filename, size, limit):
    from app.integrations.bitrix24 import documents

    content = _content(filename, size)
    remote = SimpleNamespace(
        call=AsyncMock(return_value={"NAME": filename, "SIZE": size, "DOWNLOAD_URL": "https://files.test/document"}),
        download_file=AsyncMock(return_value=content),
    )
    db = SimpleNamespace(scalar=AsyncMock(return_value=None), add=Mock(), flush=AsyncMock())
    receipt = SimpleNamespace(member_id="test-member", attempts=0, error_code=None)
    upload = AsyncMock(return_value="uploads/imported")
    monkeypatch.setattr(documents, "upload_file_async", upload)

    result = await documents._import_remote_files(
        db,
        remote,
        receipt,
        local_client=SimpleNamespace(id=uuid4()),
        parent_id="42",
        files=[{"id": "700"}],
        remote_entity_type="test_file",
    )

    assert result is True
    remote.download_file.assert_awaited_once_with("https://files.test/document", max_bytes=limit)
    upload.assert_awaited_once_with(content, filename, file_policy.mime_type_for_filename(filename))
    assert db.add.call_args_list[0].args[0].size == size


@pytest.mark.asyncio
@pytest.mark.parametrize(("filename", "size"), [("documents.zip", 161), ("document.pdf", 17)])
async def test_bitrix_import_rejects_announced_oversized_file_before_download(
    monkeypatch, small_limits, filename, size
):
    from app.integrations.bitrix24 import documents

    remote = SimpleNamespace(
        call=AsyncMock(return_value={"NAME": filename, "SIZE": size, "DOWNLOAD_URL": "https://files.test/document"}),
        download_file=AsyncMock(),
    )
    db = SimpleNamespace(scalar=AsyncMock(return_value=None), add=Mock())
    receipt = SimpleNamespace(member_id="test-member", attempts=0, error_code=None)
    upload = AsyncMock()
    monkeypatch.setattr(documents, "upload_file_async", upload)

    result = await documents._import_remote_files(
        db,
        remote,
        receipt,
        local_client=SimpleNamespace(id=uuid4()),
        parent_id="42",
        files=[{"id": "700"}],
        remote_entity_type="test_file",
    )

    assert result is False
    assert receipt.status == "failed"
    assert receipt.error_code == "FILE_TOO_LARGE"
    remote.download_file.assert_not_awaited()
    upload.assert_not_awaited()
    db.add.assert_not_called()
