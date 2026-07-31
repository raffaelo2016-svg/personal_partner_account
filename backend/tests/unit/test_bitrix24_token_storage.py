import pytest

from app.config import settings
from app.integrations.bitrix24.token_storage import TokenStorageError, _encryption_key


def test_token_storage_requires_long_separate_key(monkeypatch):
    monkeypatch.setattr(settings, "BITRIX_TOKEN_ENCRYPTION_KEY", "short")

    with pytest.raises(TokenStorageError, match="32"):
        _encryption_key()


def test_token_storage_accepts_long_key(monkeypatch):
    monkeypatch.setattr(settings, "BITRIX_TOKEN_ENCRYPTION_KEY", "x" * 32)

    assert _encryption_key() == "x" * 32
