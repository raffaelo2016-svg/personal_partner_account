import asyncio
import smtplib
import ssl
from email.message import EmailMessage

import structlog

from app.config import settings

logger = structlog.get_logger()


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
    sender = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    if not settings.SMTP_HOST or not sender:
        logger.error("password_reset_email_not_configured")
        return False

    message = EmailMessage()
    message["Subject"] = "Восстановление пароля — ЮРИТЕХ"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Вы запросили восстановление пароля в партнёрском кабинете ЮРИТЕХ.\n\n"
        f"Установить новый пароль: {reset_url}\n\n"
        f"Ссылка действует {settings.PASSWORD_RESET_EXPIRE_MINUTES} минут. "
        "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
    )

    try:
        await asyncio.to_thread(_send_message, message)
    except Exception as exc:  # noqa: BLE001
        logger.error("password_reset_email_failed", error_type=type(exc).__name__)
        return False
    return True
