from __future__ import annotations

import base64
import html
import mimetypes
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.chat import ChatMessage, ChatMessageEvent, ChatRoom
from app.models.partner import Partner
from app.services.s3_service import download_file_async, upload_file_async

logger = structlog.get_logger()

CHAT_MESSAGE_ENTITY_TYPE = "chat_message"
CHAT_MESSAGE_METHOD = "im.message.add"
CHAT_FILE_METHOD = "im.v2.File.upload"
CHAT_EVENT_SUBSCRIPTION_MAX_AGE = timedelta(hours=24)
CHAT_IMPORT_MAX_BYTES = 10 * 1024 * 1024
CHAT_FILE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}


def normalize_dialog_id(value: str) -> str:
    dialog_id = value.strip()
    if dialog_id.lower().startswith(("chat", "sg")):
        return dialog_id
    return f"chat{dialog_id}"


def _dialog_variants(value: str) -> set[str]:
    normalized = value.strip().lower()
    variants = {normalized}
    if normalized.startswith("chat"):
        variants.add(normalized[4:])
    elif normalized.startswith("sg"):
        variants.add(normalized[2:])
    elif normalized:
        variants.add(f"chat{normalized}")
    return variants


async def schedule_chat_message(
    db: AsyncSession,
    message: ChatMessage,
    *,
    room: ChatRoom | None = None,
    retry: bool = False,
) -> bool:
    room = room or await db.get(ChatRoom, message.room_id)
    if room is None or room.type != "admin" or message.origin == "bitrix":
        return False
    partner = await db.get(Partner, room.partner_id)
    if partner is None or not partner.bitrix_chat_id:
        message.bitrix_sync_status = "not_scheduled"
        message.bitrix_sync_error_code = "CHAT_NOT_LINKED"
        message.delivery_status = "failed"
        return False
    installation = await active_installation(db)
    if installation is None:
        message.bitrix_sync_status = "not_scheduled"
        message.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND"
        message.delivery_status = "failed"
        return False
    if message.bitrix_message_id:
        message.bitrix_sync_status = "synced"
        message.bitrix_sync_error_code = None
        return False

    operation_key = f"chat:message:{message.id}:v1"
    operation = await db.scalar(
        select(BitrixOutboxOperation).where(
            BitrixOutboxOperation.member_id == installation.member_id,
            BitrixOutboxOperation.operation_key == operation_key,
        )
    )
    if operation is not None:
        if retry and operation.status == "failed":
            operation.status = "pending"
            operation.attempts = 0
            operation.error_code = None
            operation.next_attempt_at = None
            operation.locked_at = None
            operation.completed_at = None
            operation.result_reference = None
        elif operation.status in {"pending", "processing", "retry", "completed"}:
            return False
    else:
        if message.attachment_s3_key:
            method = CHAT_FILE_METHOD
            payload = {
                "dialog_id": normalize_dialog_id(partner.bitrix_chat_id),
                "s3_key": message.attachment_s3_key,
                "name": message.attachment_filename or f"file-{message.id}",
                "message": message.text,
            }
        else:
            method = CHAT_MESSAGE_METHOD
            payload = {
                "DIALOG_ID": normalize_dialog_id(partner.bitrix_chat_id),
                "MESSAGE": message.text,
                "SYSTEM": "N",
                "URL_PREVIEW": "Y",
            }
        await db.execute(
            insert(BitrixOutboxOperation)
            .values(
                id=uuid.uuid4(),
                member_id=installation.member_id,
                operation_key=operation_key,
                local_entity_type=CHAT_MESSAGE_ENTITY_TYPE,
                local_entity_id=message.id,
                bitrix_method=method,
                payload=payload,
                correlation_id=uuid.uuid4(),
                max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        )

    message.bitrix_sync_status = "pending"
    message.bitrix_sync_error_code = None
    message.delivery_status = "sent"
    message.bitrix_sync_requested_at = datetime.now(UTC)
    await db.flush()
    return True


async def execute_chat_message(client: Bitrix24Client, operation: BitrixOutboxOperation) -> Any:
    if operation.bitrix_method == CHAT_FILE_METHOD:
        content = await download_file_async(str(operation.payload["s3_key"]))
        return await client.call(
            CHAT_FILE_METHOD,
            {
                "dialogId": operation.payload["dialog_id"],
                "fields": {
                    "name": operation.payload["name"],
                    "content": base64.b64encode(content).decode("ascii"),
                    "message": operation.payload.get("message") or "",
                },
            },
        )
    return await client.call(CHAT_MESSAGE_METHOD, operation.payload)


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


def _parse_event(event: Any) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(event, dict) or str(event.get("type", "")).upper() != "ONIMV2MESSAGEADD":
        return None
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    message = data.get("message")
    chat = data.get("chat")
    if not isinstance(message, dict) or not isinstance(chat, dict):
        return None
    remote_id = str(message.get("id") or "").strip()
    dialog_id = str(chat.get("dialogId") or message.get("chatId") or "").strip()
    if not remote_id or not dialog_id:
        return None
    return remote_id, data


async def _partner_for_dialog(db: AsyncSession, dialog_id: str) -> Partner | None:
    partners = list((await db.scalars(select(Partner).where(Partner.bitrix_chat_id.is_not(None)))).all())
    incoming = _dialog_variants(dialog_id)
    return next((partner for partner in partners if incoming & _dialog_variants(partner.bitrix_chat_id or "")), None)


def _event_file(data: dict[str, Any]) -> dict[str, Any] | None:
    message = data.get("message")
    params = message.get("params") if isinstance(message, dict) else None
    raw = data.get("files") or (params.get("files") if isinstance(params, dict) else None)
    if isinstance(raw, dict):
        values = list(raw.values())
    elif isinstance(raw, list):
        values = raw
    elif raw:
        values = [raw]
    else:
        values = []
    if not values:
        return None
    first = values[0]
    return first if isinstance(first, dict) else {"id": first}


async def _import_attachment(
    client: Bitrix24Client,
    installation: BitrixInstallation,
    *,
    dialog_id: str,
    file_data: dict[str, Any],
) -> tuple[str, str, int, str] | None:
    file_id = file_data.get("id") or file_data.get("fileId")
    if not file_id:
        return None
    name = PurePosixPath(str(file_data.get("name") or f"file-{file_id}")).name
    extension = PurePosixPath(name).suffix.lower()
    if extension not in CHAT_FILE_EXTENSIONS:
        return None
    declared_size = file_data.get("size")
    if isinstance(declared_size, int) and declared_size > CHAT_IMPORT_MAX_BYTES:
        return None

    result = await client.call("im.v2.File.download", {"dialogId": dialog_id, "fileId": file_id})
    download_url = result.get("downloadUrl") if isinstance(result, dict) else None
    if not isinstance(download_url, str):
        return None
    parsed = urlparse(download_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != installation.portal_domain.lower():
        raise Bitrix24Error("UNSAFE_DOWNLOAD_URL", "Chat file download URL has an unexpected host")
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
        response = await http.get(download_url)
        response.raise_for_status()
    content = response.content
    if len(content) > CHAT_IMPORT_MAX_BYTES:
        return None
    mime_type = str(file_data.get("mimeType") or mimetypes.guess_type(name)[0] or "application/octet-stream")
    s3_key = await upload_file_async(content, name, mime_type)
    return s3_key, name, len(content), mime_type


async def import_message_event(
    db: AsyncSession,
    event: Any,
    *,
    client: Bitrix24Client | None = None,
    installation: BitrixInstallation | None = None,
) -> ChatMessage | None:
    parsed = _parse_event(event)
    if parsed is None:
        return None
    remote_id, data = parsed
    existing = await db.scalar(select(ChatMessage).where(ChatMessage.bitrix_message_id == remote_id))
    if existing is not None:
        return None

    message_data = data["message"]
    chat_data = data["chat"]
    partner = await _partner_for_dialog(db, str(chat_data.get("dialogId") or message_data.get("chatId")))
    if partner is None:
        return None
    room = await db.scalar(
        select(ChatRoom).where(ChatRoom.partner_id == partner.id, ChatRoom.type == "admin")
    )
    if room is None:
        room = ChatRoom(partner_id=partner.id, type="admin")
        db.add(room)
        await db.flush()

    text = html.escape(str(message_data.get("text") or "").strip(), quote=True)
    attachment = None
    file_data = _event_file(data)
    dialog_id = str(chat_data.get("dialogId") or message_data.get("chatId"))
    if file_data and client is not None and installation is not None:
        attachment = await _import_attachment(
            client,
            installation,
            dialog_id=dialog_id,
            file_data=file_data,
        )
    if not text and attachment is None:
        return None
    created_at = datetime.now(UTC)
    raw_date = message_data.get("date") or event.get("date")
    if isinstance(raw_date, str):
        with suppress(ValueError):
            created_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

    attachment_s3_key, attachment_filename, attachment_size, attachment_mime_type = attachment or (
        None,
        None,
        None,
        None,
    )
    message = ChatMessage(
        room_id=room.id,
        sender_id=None,
        sender_type="admin",
        text=text,
        delivery_status="delivered",
        origin="bitrix",
        bitrix_sync_status="synced",
        bitrix_message_id=remote_id,
        bitrix_author_id=str(message_data.get("authorId") or "") or None,
        bitrix_synced_at=datetime.now(UTC),
        attachment_s3_key=attachment_s3_key,
        attachment_filename=attachment_filename,
        attachment_size=attachment_size,
        attachment_mime_type=attachment_mime_type,
        created_at=created_at,
    )
    db.add(message)
    await db.flush()
    return message


async def record_message_change_event(
    db: AsyncSession,
    event: Any,
    *,
    member_id: str,
) -> bool:
    if not isinstance(event, dict):
        return False
    remote_event_type = str(event.get("type") or "").upper()
    event_type = {
        "ONIMV2MESSAGEUPDATE": "updated",
        "ONIMV2MESSAGEDELETE": "deleted",
    }.get(remote_event_type)
    if event_type is None:
        return False
    event_id = event.get("eventId")
    data = event.get("data")
    if not isinstance(event_id, int) or isinstance(event_id, bool) or not isinstance(data, dict):
        return False
    message_data = data.get("message")
    chat_data = data.get("chat")
    if not isinstance(message_data, dict) or not isinstance(chat_data, dict):
        return False
    remote_message_id = str(message_data.get("id") or "").strip()
    dialog_id = str(chat_data.get("dialogId") or message_data.get("chatId") or "").strip()
    if not remote_message_id or not dialog_id:
        return False
    partner = await _partner_for_dialog(db, dialog_id)
    if partner is None:
        return False
    room = await db.scalar(select(ChatRoom).where(ChatRoom.partner_id == partner.id, ChatRoom.type == "admin"))
    if room is None:
        return False
    local_message = await db.scalar(select(ChatMessage).where(ChatMessage.bitrix_message_id == remote_message_id))
    raw_date = event.get("date") or message_data.get("date")
    event_at = datetime.now(UTC)
    if isinstance(raw_date, str):
        with suppress(ValueError):
            event_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    statement = (
        insert(ChatMessageEvent)
        .values(
            id=uuid.uuid4(),
            member_id=member_id,
            room_id=room.id,
            chat_message_id=local_message.id if local_message else None,
            bitrix_event_id=event_id,
            bitrix_message_id=remote_message_id,
            event_type=event_type,
            actor_id=str(message_data.get("authorId") or "") or None,
            event_at=event_at,
        )
        .on_conflict_do_nothing(constraint="uq_chat_message_events_remote")
        .returning(ChatMessageEvent.id)
    )
    return await db.scalar(statement) is not None


async def poll_chat_events(db: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    installation = await active_installation(db)
    if installation is None:
        return {"received": 0, "imported": 0, "journaled": 0}
    token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, token) as client:
        subscribed_at = installation.im_event_subscribed_at
        if subscribed_at is None or subscribed_at < datetime.now(UTC) - CHAT_EVENT_SUBSCRIPTION_MAX_AGE:
            await client.call("im.v2.Event.subscribe", {})
            installation.im_event_subscribed_at = datetime.now(UTC)

        params: dict[str, Any] = {"limit": limit}
        if installation.im_event_offset is not None:
            params["offset"] = installation.im_event_offset
        result = await client.call("im.v2.Event.get", params)
        if not isinstance(result, dict):
            raise Bitrix24Error("INVALID_RESPONSE", "Chat event queue returned an unexpected response")
        events = result.get("events")
        if not isinstance(events, list):
            raise Bitrix24Error("INVALID_RESPONSE", "Chat event queue returned an unexpected event list")

        imported = 0
        journaled = 0
        for event in events:
            if await import_message_event(db, event, client=client, installation=installation) is not None:
                imported += 1
            elif await record_message_change_event(db, event, member_id=installation.member_id):
                journaled += 1
    next_offset = result.get("nextOffset")
    if isinstance(next_offset, int) and not isinstance(next_offset, bool):
        installation.im_event_offset = next_offset
    await db.commit()
    return {"received": len(events), "imported": imported, "journaled": journaled}
