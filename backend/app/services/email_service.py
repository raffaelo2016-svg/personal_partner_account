import asyncio
import hashlib
import smtplib
import ssl
from email.message import EmailMessage

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

RESEND_EMAILS_URL = "https://api.resend.com/emails"


def _password_reset_text(reset_url: str) -> str:
    return (
        "Вы запросили восстановление пароля в партнёрском кабинете ЮРИТЕХ.\n\n"
        f"Установить новый пароль: {reset_url}\n\n"
        f"Ссылка действует {settings.PASSWORD_RESET_EXPIRE_MINUTES} минут. "
        "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
    )


async def _send_via_resend(recipient: str, reset_url: str) -> None:
    idempotency_key = hashlib.sha256(reset_url.encode()).hexdigest()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            RESEND_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Idempotency-Key": f"password-reset-{idempotency_key}",
            },
            json={
                "from": settings.RESEND_FROM_EMAIL,
                "to": [recipient],
                "subject": "Восстановление пароля — ЮРИТЕХ",
                "text": _password_reset_text(reset_url),
            },
        )
        response.raise_for_status()


def _send_message(message: EmailMessage) -> None:
    if settings.SMTP_USE_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=context) as smtp:
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_USE_STARTTLS:
            smtp.starttls(context=ssl.create_default_context())
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def send_password_reset_email(recipient: str, reset_url: str) -> bool:
    if settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL:
        try:
            await _send_via_resend(recipient, reset_url)
        except Exception as exc:  # noqa: BLE001
            logger.error("password_reset_email_failed", provider="resend", error_type=type(exc).__name__)
            return False
        return True

    sender = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    if not settings.SMTP_HOST or not sender:
        logger.error("password_reset_email_not_configured")
        return False

    message = EmailMessage()
    message["Subject"] = "Восстановление пароля — ЮРИТЕХ"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(_password_reset_text(reset_url))

    try:
        await asyncio.to_thread(_send_message, message)
    except Exception as exc:  # noqa: BLE001
        logger.error("password_reset_email_failed", provider="smtp", error_type=type(exc).__name__)
        return False
    return True


def _invite_text(invite_url: str, role_label: str, inviter_label: str, expires_at: str) -> str:
    return (
        f"{inviter_label} пригласил(а) вас в кабинет ЮРИТЕХ с ролью «{role_label}».\n\n"
        f"Создать личный аккаунт: {invite_url}\n\n"
        f"Ссылка действует до {expires_at} и может быть использована один раз. "
        "Почта закреплена за приглашением — изменить её нельзя.\n\n"
        "Если вы не ожидали это письмо, просто проигнорируйте его."
    )


async def _send_invite_via_resend(recipient: str, subject: str, text: str, seed: str) -> None:
    idempotency_key = hashlib.sha256(seed.encode()).hexdigest()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            RESEND_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Idempotency-Key": f"invite-{idempotency_key}",
            },
            json={
                "from": settings.RESEND_FROM_EMAIL,
                "to": [recipient],
                "subject": subject,
                "text": text,
            },
        )
        response.raise_for_status()


async def send_invite_email(
    recipient: str,
    invite_url: str,
    role_label: str,
    inviter_label: str,
    expires_at: str,
) -> bool:
    """Письмо-приглашение администратора. Возвращает False, если почта не настроена."""
    subject = "Доступ в кабинет ЮРИТЕХ — приглашение"
    text = _invite_text(invite_url, role_label, inviter_label, expires_at)

    if settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL:
        try:
            await _send_invite_via_resend(recipient, subject, text, invite_url)
        except Exception as exc:  # noqa: BLE001
            logger.error("invite_email_failed", provider="resend", error_type=type(exc).__name__)
            return False
        return True

    sender = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    if not settings.SMTP_HOST or not sender:
        logger.warning("invite_email_not_configured", recipient=recipient)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text)

    try:
        await asyncio.to_thread(_send_message, message)
    except Exception as exc:  # noqa: BLE001
        logger.error("invite_email_failed", provider="smtp", error_type=type(exc).__name__)
        return False
    return True
