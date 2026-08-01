from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.integrations.bitrix24 import survey_cli


class FakeSession:
    def __init__(self, installation):
        self.installation = installation

    async def scalar(self, _query):
        return self.installation


@pytest.mark.asyncio
async def test_stored_credentials_decrypts_access_token_without_returning_ciphertext(monkeypatch):
    encrypted = b"encrypted-access-token"
    installation = SimpleNamespace(
        client_endpoint="https://bitrix.example/rest/",
        access_token_encrypted=encrypted,
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    async def fake_decrypt(db, value):
        assert isinstance(db, FakeSession)
        assert value == encrypted
        return "decrypted-token"

    monkeypatch.setattr(survey_cli, "decrypt_token", fake_decrypt)

    endpoint, token, refreshed = await survey_cli._stored_credentials(FakeSession(installation), "BITRIX.EXAMPLE")

    assert endpoint == "https://bitrix.example/rest/"
    assert token == "decrypted-token"
    assert refreshed is False


@pytest.mark.asyncio
async def test_stored_credentials_refreshes_expired_token(monkeypatch):
    installation = SimpleNamespace(
        client_endpoint="https://bitrix.example/rest/",
        access_token_encrypted=b"old-access",
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    async def fake_refresh(db, selected_installation):
        assert isinstance(db, FakeSession)
        assert selected_installation is installation
        return "new-access"

    monkeypatch.setattr(survey_cli, "refresh_installation_tokens", fake_refresh)

    endpoint, token, refreshed = await survey_cli._stored_credentials(FakeSession(installation), "bitrix.example")

    assert endpoint == "https://bitrix.example/rest/"
    assert token == "new-access"
    assert refreshed is True


@pytest.mark.asyncio
async def test_stored_credentials_requires_installed_portal():
    with pytest.raises(SystemExit, match="No encrypted Bitrix24 installation"):
        await survey_cli._stored_credentials(FakeSession(None), "bitrix.example")
