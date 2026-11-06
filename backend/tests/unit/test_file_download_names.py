from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.api import files
from app.models.file_upload import FileUpload


@pytest.fixture
def setup_db():
    """Database access is mocked for these API regression tests."""


@pytest.fixture
def record():
    return FileUpload(
        id=uuid4(),
        client_id=uuid4(),
        original_name="Справка об открытых банковских счетах.pdf",
        s3_key="uploads/technical-uuid.pdf",
        size=123,
        mime_type="application/pdf",
        document_type="other",
        created_at=datetime.now(UTC),
        bitrix_sync_status="synced",
    )


async def test_list_passes_stored_name_to_storage(monkeypatch, record):
    result = Mock()
    result.scalars.return_value.all.return_value = [record]
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    signer = Mock(return_value="https://files.test/signed")
    monkeypatch.setattr(files, "_check_client_access", AsyncMock())
    monkeypatch.setattr(files, "sync_client_initial_documents", AsyncMock())
    monkeypatch.setattr(files, "get_presigned_url", signer)

    response = await files.list_client_files(str(record.client_id), db, SimpleNamespace(role="admin"))

    assert response[0].filename == record.original_name
    signer.assert_called_once_with(record.s3_key, filename=record.original_name)


@pytest.mark.parametrize("endpoint", [files.get_file_url, files.retry_file_bitrix_endpoint])
async def test_file_link_passes_stored_name_to_storage(monkeypatch, record, endpoint):
    db = SimpleNamespace(get=AsyncMock(return_value=record), commit=AsyncMock())
    signer = AsyncMock(return_value="https://files.test/signed")
    monkeypatch.setattr(files, "_check_client_access", AsyncMock())
    monkeypatch.setattr(files, "schedule_file_creation", AsyncMock())
    monkeypatch.setattr(files, "get_presigned_url_async", signer)

    response = await endpoint(str(record.id), db, SimpleNamespace(role="admin"))

    assert response.filename == record.original_name
    signer.assert_awaited_once_with(record.s3_key, filename=record.original_name)
