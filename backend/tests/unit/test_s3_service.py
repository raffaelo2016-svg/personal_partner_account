from unittest.mock import MagicMock

import pytest
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
