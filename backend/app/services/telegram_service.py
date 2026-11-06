from __future__ import annotations

import html
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.settings import NotificationPreference

logger = structlog.get_logger()


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


async def send_telegram_message(
    chat_id: int,
    text: str,
    *,
    link: str | None = None,
) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        return False

    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if link:
        absolute_link = urljoin(settings.PUBLIC_APP_URL.rstrip("/") + "/", link.lstrip("/"))
        parsed = urlparse(absolute_link)
        if parsed.scheme in {"http", "https"}:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": "Открыть в кабинете", "url": absolute_link}]],
            }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(_api_url("sendMessage"), json=payload)
            response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("telegram_send_failed", chat_id=chat_id, error=str(exc))
        return False


async def connect_chat_from_start(
    db: AsyncSession,
    *,
    token: str,
    chat_id: int,
    username: str | None,
) -> bool:
    token_hash = sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.telegram_connect_token_hash == token_hash,
            NotificationPreference.telegram_connect_expires_at > datetime.now(UTC),
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return False

    # One Telegram chat can be linked to only one cabinet account.
    previous = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.telegram_chat_id == chat_id,
            NotificationPreference.user_id != pref.user_id,
        )
    )
    for other in previous.scalars().all():
        other.telegram_chat_id = None
        other.telegram_username = None
        other.telegram_connected_at = None

    pref.telegram_chat_id = chat_id
    pref.telegram_username = username
    pref.telegram_connected_at = datetime.now(UTC)
    pref.telegram_connect_token_hash = None
    pref.telegram_connect_expires_at = None
    pref.telegram_notifications = True
    await db.commit()
    logger.info("telegram_connected", user_id=str(pref.user_id))
    return True


async def disconnect_chat(db: AsyncSession, chat_id: int) -> bool:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.telegram_chat_id == chat_id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return False
    pref.telegram_chat_id = None
    pref.telegram_username = None
    pref.telegram_connected_at = None
    await db.commit()
    return True


async def deliver_notification(
    db: AsyncSession,
    *,
    user_id: str,
    title: str,
    message: str,
    link: str | None,
) -> bool:
    pref = await db.get(NotificationPreference, user_id)
    if not pref or not pref.telegram_notifications or pref.telegram_chat_id is None:
        return False
    text = f"<b>{html.escape(title)}</b>\n\n{html.escape(message)}"
    return await send_telegram_message(pref.telegram_chat_id, text, link=link)
