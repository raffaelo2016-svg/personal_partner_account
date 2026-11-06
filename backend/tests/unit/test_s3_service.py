from unittest.mock import MagicMock
from urllib.parse import parse_qs, unquote, urlsplit

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

from app.services import s3_service


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "safe test error"}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "HeadBucket",
    )


def test_missing_bucket_is_created(monkeypatch: pytest.MonkeyPatch):
    client = MagicMock()
    client.head_bucket.side_effect = _client_error("NoSuchBucket", 404)
    monkeypatch.setattr(s3_service, "_s3_client", None)
    monkeypatch.setattr(s3_service, "_build_client", MagicMock(return_value=client))

    assert s3_service._get_s3() is client
    client.create_bucket.assert_called_once_with(Bucket=s3_service.settings.S3_BUCKET)


def test_access_denied_is_not_misreported_as_missing_bucket(monkeypatch: pytest.MonkeyPatch):
    client = MagicMock()
    client.head_bucket.side_effect = _client_error("403", 403)
    monkeypatch.setattr(s3_service, "_s3_client", None)
    monkeypatch.setattr(s3_service, "_build_client", MagicMock(return_value=client))

    with pytest.raises(ClientError):
        s3_service._get_s3()

    client.create_bucket.assert_not_called()
    assert s3_service._s3_client is None


@pytest.fixture
def signing_client(monkeypatch):
    client = boto3.client(
        "s3",
        endpoint_url="https://files.example.test",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )
    monkeypatch.setattr(s3_service, "_s3_public_client", client)


@pytest.mark.parametrize("filename", [
    "Справка об открытых банковских счетах.pdf",
    "Документы № 2 (копия).zip",
    "Заявление.docx",
    "report 100% #1.pdf",
    'Справка "Банк"; 2026.pdf',
])
def test_presigned_url_preserves_original_filename(signing_client, filename):
    url = s3_service.get_presigned_url("uploads/uuid.pdf", filename=filename)
    query = parse_qs(urlsplit(url).query)
    disposition = query["response-content-disposition"][0]
    assert disposition.startswith("inline; filename*=UTF-8''")
    assert unquote(disposition.split("''", 1)[1]) == filename
    assert query["X-Amz-Signature"]
    assert query["X-Amz-Expires"] == ["900"]


def test_presigned_url_without_filename_stays_compatible(signing_client):
    url = s3_service.get_presigned_url("uploads/uuid.pdf", 60)
    query = parse_qs(urlsplit(url).query)
    assert "response-content-disposition" not in query
    assert query["X-Amz-Expires"] == ["60"]


async def test_async_presigned_url_preserves_filename(signing_client):
    url = await s3_service.get_presigned_url_async("uploads/uuid.pdf", filename="Справка.pdf")
    disposition = parse_qs(urlsplit(url).query)["response-content-disposition"][0]
    assert unquote(disposition.split("''", 1)[1]) == "Справка.pdf"


def test_filename_cannot_inject_response_headers(signing_client):
    url = s3_service.get_presigned_url("uploads/uuid.pdf", filename="report\r\nX-Test: value.pdf")
    disposition = parse_qs(urlsplit(url).query)["response-content-disposition"][0]
    assert "\r" not in disposition
    assert "\n" not in disposition
    assert "%0D%0A" in disposition


@pytest.mark.parametrize("filename", [r"C:\documents\Справка.pdf", "/documents/Справка.pdf"])
def test_filename_does_not_include_local_path(signing_client, filename):
    url = s3_service.get_presigned_url("uploads/uuid.pdf", filename=filename)
    disposition = parse_qs(urlsplit(url).query)["response-content-disposition"][0]
    assert unquote(disposition.split("''", 1)[1]) == "Справка.pdf"
