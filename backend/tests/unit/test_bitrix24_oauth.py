from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import settings
from app.integrations.bitrix24 import oauth
from app.integrations.bitrix24.client import Bitrix24Error


class FakeSession:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


def test_rejects_untrusted_oauth_endpoint():
    with pytest.raises(Bitrix24Error, match="not allowed"):
        oauth._token_endpoint("https://example.com/rest/")


def test_uses_central_oauth_host_for_regional_endpoint():
    assert (
        oauth._token_endpoint("https://oauth.bitrix24.tech/rest/")
        == "https://oauth.bitrix.info/oauth/token/"
    )


@pytest.mark.asyncio
async def test_refresh_rotates_and_encrypts_both_tokens(monkeypatch):
    monkeypatch.setattr(settings, "BITRIX_CLIENT_ID", "local.app")
    monkeypatch.setattr(settings, "BITRIX_CLIENT_SECRET", "application-secret")
    encrypted_values: list[str] = []

    async def fake_decrypt(_db, value):
        assert value == b"encrypted-refresh"
        return "old-refresh"

    async def fake_encrypt(_db, value):
        encrypted_values.append(value)
        return f"encrypted:{value}".encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "oauth.bitrix.info"
        query = parse_qs(request.url.query.decode())
        assert query["client_secret"] == ["application-secret"]
        assert query["refresh_token"] == ["old-refresh"]
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
                "member_id": "member-1",
                "scope": "crm,user",
                "status": "L",
            },
        )

    monkeypatch.setattr(oauth, "decrypt_token", fake_decrypt)
    monkeypatch.setattr(oauth, "encrypt_token", fake_encrypt)
    installation = SimpleNamespace(
        member_id="member-1",
        server_endpoint="https://oauth.bitrix24.tech/rest/",
        refresh_token_encrypted=b"encrypted-refresh",
        access_token_encrypted=b"old-access",
        token_expires_at=None,
        scope="",
        status="L",
    )
    db = FakeSession()

    token = await oauth.refresh_installation_tokens(db, installation, transport=httpx.MockTransport(handler))

    assert token == "new-access"
    assert encrypted_values == ["new-access", "new-refresh"]
    assert installation.access_token_encrypted == b"encrypted:new-access"
    assert installation.refresh_token_encrypted == b"encrypted:new-refresh"
    assert isinstance(installation.token_expires_at, datetime)
    assert installation.token_expires_at.tzinfo is UTC
    assert db.committed is True


@pytest.mark.asyncio
async def test_refresh_error_does_not_expose_credentials(monkeypatch):
    monkeypatch.setattr(settings, "BITRIX_CLIENT_ID", "local.app")
    monkeypatch.setattr(settings, "BITRIX_CLIENT_SECRET", "top-secret")

    async def fake_decrypt(_db, _value):
        return "refresh-secret"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_grant", "error_description": "Denied"})

    monkeypatch.setattr(oauth, "decrypt_token", fake_decrypt)
    installation = SimpleNamespace(
        member_id="member-1",
        server_endpoint="https://oauth.bitrix24.tech/rest/",
        refresh_token_encrypted=b"ciphertext",
    )

    with pytest.raises(Bitrix24Error) as exc_info:
        await oauth.refresh_installation_tokens(FakeSession(), installation, transport=httpx.MockTransport(handler))

    assert exc_info.value.code == "invalid_grant"
    assert "top-secret" not in str(exc_info.value)
    assert "refresh-secret" not in str(exc_info.value)
