from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.token_storage import decrypt_token, encrypt_token
from app.models.bitrix_installation import BitrixInstallation

_ALLOWED_OAUTH_HOSTS = {"oauth.bitrix.info", "oauth.bitrix24.tech"}


def _token_endpoint(server_endpoint: str) -> str:
    parsed = urlparse(server_endpoint.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _ALLOWED_OAUTH_HOSTS:
        raise Bitrix24Error("INVALID_OAUTH_ENDPOINT", "Bitrix24 OAuth endpoint is not allowed")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise Bitrix24Error("INVALID_OAUTH_ENDPOINT", "Bitrix24 OAuth endpoint is invalid")
    return f"https://{host}/oauth/token/"


def _expiry(payload: dict[str, Any]) -> datetime:
    try:
        if payload.get("expires"):
            return datetime.fromtimestamp(int(payload["expires"]), tz=UTC)
        if payload.get("expires_in"):
            return datetime.now(UTC) + timedelta(seconds=int(payload["expires_in"]))
    except (TypeError, ValueError, OverflowError):
        pass
    return datetime.now(UTC) + timedelta(minutes=55)


async def refresh_installation_tokens(
    db: AsyncSession,
    installation: BitrixInstallation,
    *,
    timeout: float = 20.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Rotate one Bitrix24 OAuth token pair and persist it encrypted."""
    if not settings.BITRIX_CLIENT_ID or not settings.BITRIX_CLIENT_SECRET:
        raise Bitrix24Error("OAUTH_NOT_CONFIGURED", "Bitrix24 application credentials are not configured")

    refresh_token = await decrypt_token(db, installation.refresh_token_encrypted)
    params = {
        "grant_type": "refresh_token",
        "client_id": settings.BITRIX_CLIENT_ID,
        "client_secret": settings.BITRIX_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.get(_token_endpoint(installation.server_endpoint), params=params)
    except httpx.TimeoutException as exc:
        raise Bitrix24Error("TIMEOUT", "Bitrix24 OAuth server did not respond in time") from exc
    except httpx.HTTPError as exc:
        raise Bitrix24Error("TRANSPORT_ERROR", "Could not reach Bitrix24 OAuth server") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 OAuth server returned non-JSON response") from exc
    if not isinstance(payload, dict):
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 OAuth server returned an unexpected response")
    if response.is_error or payload.get("error"):
        raise Bitrix24Error(
            str(payload.get("error", f"HTTP_{response.status_code}")),
            "OAuth token refresh failed",
            status_code=response.status_code,
        )

    access_token = payload.get("access_token")
    next_refresh_token = payload.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 OAuth response has no access token")
    if not isinstance(next_refresh_token, str) or not next_refresh_token:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 OAuth response has no refresh token")
    if payload.get("member_id") and payload["member_id"] != installation.member_id:
        raise Bitrix24Error("INSTALLATION_MISMATCH", "Bitrix24 OAuth response belongs to another installation")

    installation.access_token_encrypted = await encrypt_token(db, access_token)
    installation.refresh_token_encrypted = await encrypt_token(db, next_refresh_token)
    installation.token_expires_at = _expiry(payload)
    if isinstance(payload.get("scope"), str):
        installation.scope = payload["scope"]
    if isinstance(payload.get("status"), str):
        installation.status = payload["status"]
    await db.commit()
    return access_token
