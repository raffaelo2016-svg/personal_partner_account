from unittest.mock import AsyncMock

import pytest

from app.services import email_service


@pytest.mark.asyncio
async def test_password_reset_email_prefers_resend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(email_service.settings, "RESEND_API_KEY", "test-api-key")
    monkeypatch.setattr(email_service.settings, "RESEND_FROM_EMAIL", "ЮРИТЕХ <noreply@example.com>")
    send_via_resend = AsyncMock()
    monkeypatch.setattr(email_service, "_send_via_resend", send_via_resend)

    delivered = await email_service.send_password_reset_email(
        "partner@example.com",
        "https://example.com/reset-password?token=secret",
    )

    assert delivered is True
    send_via_resend.assert_awaited_once_with(
        "partner@example.com",
        "https://example.com/reset-password?token=secret",
    )


@pytest.mark.asyncio
async def test_password_reset_email_is_disabled_without_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(email_service.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(email_service.settings, "RESEND_FROM_EMAIL", "")
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "")
    monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_service.settings, "SMTP_FROM_EMAIL", "")

    delivered = await email_service.send_password_reset_email(
        "partner@example.com",
        "https://example.com/reset-password?token=secret",
    )

    assert delivered is False
