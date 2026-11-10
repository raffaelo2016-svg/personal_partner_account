from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import func, select
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
from app.validation.files import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, has_valid_signature, normalize_mime_type

logger = structlog.get_logger()

CHAT_MESSAGE_ENTITY_TYPE = "chat_message"
CHAT_MESSAGE_METHOD = "im.message.add"
CHAT_FILE_METHOD = "im.v2.File.upload"
BOT_MESSAGE_METHOD = "imbot.v2.Chat.Message.send"
BOT_FILE_METHOD = "imbot.v2.File.upload"
BOT_CODE = "uritech_partner_cabinet"
CHAT_EVENT_SUBSCRIPTION_MAX_AGE = timedelta(hours=24)
CHAT_IMPORT_MAX_BYTES = MAX_FILE_SIZE_BYTES
CHAT_FILE_EXTENSIONS = ALLOWED_EXTENSIONS - {".zip"}
PARTNER_CHAT_TITLE_PREFIX = "ЮРИТЕХ — "
PARTNER_CHAT_DESCRIPTION_PREFIX = "Личный кабинет партнёра ЮРИТЕХ"
CHAT_POLL_ADVISORY_LOCK_ID = 9_172_401
REQUIRED_PARTNER_CHAT_USERS = (
    "Протацкая Тамара",
    "Швецова Тамара",
    "Агейчик Нина",
    "Самсонюк Евгений",
)


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


def _normalized_partner_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _normalized_person_name(value: str | None) -> str:
    return " ".join(re.findall(r"[\w-]+", (value or "").casefold().replace("ё", "е")))


def _bitrix_user_name(user: dict[str, Any]) -> str:
    return _normalized_person_name(
        " ".join(
            str(user.get(key) or "")
            for key in (
                "FULL_NAME",
                "fullName",
                "LAST_NAME",
                "lastName",
                "NAME",
                "name",
                "SECOND_NAME",
                "secondName",
            )
        )
    )


async def _active_support_user_ids(client: Bitrix24Client) -> list[int]:
    users = await client.list_all("user.get", {"FILTER": {"ACTIVE": True}})
    active_users = {
        int(value): user
        for user in users
        if isinstance(user, dict)
        and (value := str(user.get("ID") or user.get("id") or "")).isdigit()
        and int(value) > 0
    }
    result = [user_id for user_id in settings.bitrix_chat_support_user_ids if user_id in active_users]
    unresolved_names: list[str] = []
    for required_name in REQUIRED_PARTNER_CHAT_USERS:
        required_tokens = set(_normalized_person_name(required_name).split())
        matches = [
            user_id
            for user_id, user in active_users.items()
            if required_tokens.issubset(set(_bitrix_user_name(user).split()))
        ]
        if len(matches) != 1:
            unresolved_names.append(required_name)
            continue
        if matches[0] not in result:
            result.append(matches[0])
    if unresolved_names:
        logger.error("bitrix_partner_chat_required_users_unresolved", names=unresolved_names)
        return []
    return result


def partner_chat_is_excluded(partner: Partner) -> bool:
    searchable = " ".join(
        _normalized_partner_text(value)
        for value in (
            partner.company_name,
            partner.director_name,
            partner.short_name,
            partner.full_legal_name,
        )
        if value
    )
    return any(term in searchable for term in settings.bitrix_chat_excluded_partner_terms)


def partner_chat_title(partner: Partner) -> str:
    display_name = partner.company_name.strip() or partner.director_name.strip()
    return f"{PARTNER_CHAT_TITLE_PREFIX}{display_name}"[:255]


def partner_chat_description(partner: Partner) -> str:
    return f"{PARTNER_CHAT_DESCRIPTION_PREFIX} · partner_cabinet:{partner.id}"


def _chat_id_from_result(result: Any) -> int | None:
    candidate = result
    if isinstance(result, dict):
        chat = result.get("chat")
        candidate = chat.get("id") or chat.get("ID") if isinstance(chat, dict) else result.get("id") or result.get("ID")
    if isinstance(candidate, bool):
        return None
    if isinstance(candidate, int) and candidate > 0:
        return candidate
    if isinstance(candidate, str) and candidate.isdigit() and int(candidate) > 0:
        return int(candidate)
    return None


def _empty_poll_result() -> dict[str, int]:
    return {
        "received": 0,
        "imported": 0,
        "journaled": 0,
        "joined": 0,
        "created": 0,
        "recovered": 0,
        "excluded": 0,
        "failed": 0,
    }


def _chat_delivery_operation(
    message: ChatMessage,
    partner: Partner,
    installation: BitrixInstallation,
) -> tuple[str, dict[str, Any]]:
    dialog_id = normalize_dialog_id(partner.bitrix_chat_id or "")
    if message.attachment_s3_key:
        method = BOT_FILE_METHOD if installation.im_bot_id else CHAT_FILE_METHOD
        payload: dict[str, Any] = {
            "dialog_id": dialog_id,
            "s3_key": message.attachment_s3_key,
            "name": message.attachment_filename or f"file-{message.id}",
            "message": message.text,
        }
        if installation.im_bot_id:
            payload["bot_id"] = installation.im_bot_id
        return method, payload
    if installation.im_bot_id:
        return BOT_MESSAGE_METHOD, {
            "botId": installation.im_bot_id,
            "dialogId": dialog_id,
            "fields": {"message": message.text, "urlPreview": "Y"},
        }
    return CHAT_MESSAGE_METHOD, {
        "DIALOG_ID": dialog_id,
        "MESSAGE": message.text,
        "SYSTEM": "N",
        "URL_PREVIEW": "Y",
    }


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

    method, payload = _chat_delivery_operation(message, partner, installation)

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
            operation.bitrix_method = method
            operation.payload = payload
        elif operation.status in {"pending", "processing", "retry", "completed"}:
            return False
    else:
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
    if operation.bitrix_method in {CHAT_FILE_METHOD, BOT_FILE_METHOD}:
        content = await download_file_async(str(operation.payload["s3_key"]))
        if operation.bitrix_method == BOT_FILE_METHOD:
            return await client.call(
                BOT_FILE_METHOD,
                {
                    "botId": operation.payload["bot_id"],
                    "dialogId": operation.payload["dialog_id"],
                    "fields": {
                        "name": operation.payload["name"],
                        "content": base64.b64encode(content).decode("ascii"),
                        "message": operation.payload.get("message") or "",
                    },
                },
            )
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
    return await client.call(operation.bitrix_method, operation.payload)


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


def _parse_event(event: Any) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(event, dict) or str(event.get("type", "")).upper() not in {
        "ONIMV2MESSAGEADD",
        "ONIMBOTV2MESSAGEADD",
    }:
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
    candidates = [data.get("files"), data.get("file")]
    if isinstance(message, dict):
        candidates.extend([message.get("files"), message.get("file")])
    if isinstance(params, dict):
        candidates.extend(params.get(key) for key in ("files", "FILES", "file", "FILE", "fileId", "FILE_ID"))
    raw = next((value for value in candidates if value), None)
    if isinstance(raw, dict):
        if any(key in raw for key in ("id", "fileId", "name", "extension", "size")):
            values = [raw]
        else:
            values = []
            for key, value in raw.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("id", key)
                else:
                    item = {"id": value or key}
                values.append(item)
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


def _history_files(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    files: list[dict[str, Any]] = []
    for key, value_item in value.items():
        if not isinstance(value_item, dict):
            continue
        item = dict(value_item)
        item.setdefault("id", key)
        files.append(item)
    return files


async def _event_file_from_history(
    client: Bitrix24Client,
    *,
    dialog_id: str,
    remote_id: str,
    event_file: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Hydrate file metadata omitted from compact messenger events."""
    try:
        first_id = max(int(remote_id) - 1, 0)
    except ValueError:
        return event_file
    result = await client.call(
        "im.dialog.messages.get",
        {"DIALOG_ID": dialog_id, "FIRST_ID": first_id, "LIMIT": 5},
    )
    if not isinstance(result, dict):
        return event_file
    messages = result.get("messages")
    files = _history_files(result.get("files"))
    if not isinstance(messages, list) or not files:
        return event_file
    target = next(
        (message for message in messages if isinstance(message, dict) and str(message.get("id") or "") == remote_id),
        None,
    )
    if target is None:
        return event_file

    target_file = _event_file({"message": target})
    wanted_id = str(
        (target_file or event_file or {}).get("id") or (target_file or event_file or {}).get("fileId") or ""
    )
    matching = [
        file for file in files if isinstance(file, dict) and (not wanted_id or str(file.get("id") or "") == wanted_id)
    ]
    if len(matching) != 1:
        return event_file
    hydrated = dict(event_file or {})
    hydrated.update(matching[0])
    return hydrated


async def _reconcile_chat_file_history(
    db: AsyncSession,
    client: Bitrix24Client,
    installation: BitrixInstallation,
    *,
    partner_limit: int = 25,
    message_limit: int = 20,
) -> dict[str, int]:
    """Recover file messages that the bot event queue did not deliver."""
    partners = list(
        (
            await db.scalars(
                select(Partner)
                .where(
                    Partner.bitrix_chat_id.is_not(None),
                    Partner.bitrix_chat_bot_joined_at.is_not(None),
                )
                .order_by(Partner.bitrix_chat_bot_joined_at.desc())
                .limit(partner_limit)
            )
        ).all()
    )
    imported = 0
    scanned = 0
    for index, partner in enumerate(partners):
        dialog_id = normalize_dialog_id(partner.bitrix_chat_id or "")
        result = await client.call(
            "im.dialog.messages.get",
            {"DIALOG_ID": dialog_id, "LIMIT": message_limit},
        )
        if not isinstance(result, dict) or not isinstance(result.get("messages"), list):
            continue
        files = _history_files(result.get("files"))
        files_by_id = {str(item.get("id")): item for item in files if item.get("id") is not None}
        joined_at = partner.bitrix_chat_bot_joined_at
        if joined_at is not None and joined_at.tzinfo is None:
            joined_at = joined_at.replace(tzinfo=UTC)

        for item in reversed(result["messages"]):
            if not isinstance(item, dict):
                continue
            file_reference = _event_file({"message": item})
            file_id = (file_reference or {}).get("id") or (file_reference or {}).get("fileId")
            file_data = files_by_id.get(str(file_id))
            if file_data is None:
                continue
            raw_date = item.get("date")
            message_at: datetime | None = None
            if isinstance(raw_date, str):
                with suppress(ValueError):
                    message_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if message_at is not None and message_at.tzinfo is None:
                message_at = message_at.replace(tzinfo=UTC)
            if joined_at is not None and message_at is not None and message_at < joined_at:
                continue
            scanned += 1
            event = {
                "type": "ONIMBOTV2MESSAGEADD",
                "date": raw_date,
                "data": {
                    "message": {
                        "id": item.get("id"),
                        "chatId": item.get("chatId") or item.get("chat_id"),
                        "authorId": item.get("authorId") or item.get("author_id"),
                        "date": raw_date,
                        "text": item.get("text") or "",
                        "params": item.get("params") or {},
                    },
                    "chat": {"dialogId": dialog_id},
                    "files": [file_data],
                },
            }
            if await import_message_event(db, event, client=client, installation=installation) is not None:
                imported += 1
        if index + 1 < len(partners):
            await asyncio.sleep(0.55)
    await db.commit()
    return {"partners": len(partners), "scanned": scanned, "imported": imported}


async def reconcile_chat_file_history(db: AsyncSession) -> dict[str, int]:
    installation = await active_installation(db)
    if installation is None or installation.im_bot_id is None:
        return {"partners": 0, "scanned": 0, "imported": 0}
    token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, token) as client:
        return await _reconcile_chat_file_history(db, client, installation)


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

    if installation.im_bot_id:
        result = await client.call(
            "imbot.v2.File.download",
            {"botId": installation.im_bot_id, "fileId": file_id},
        )
    else:
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
    if extension == ".mp3":
        mime_type = normalize_mime_type(name, mime_type)
        if mime_type is None or not has_valid_signature(content, extension):
            return None
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
    if (
        installation is not None
        and installation.im_bot_id is not None
        and str(message_data.get("authorId") or "") == str(installation.im_bot_id)
    ):
        return None
    chat_data = data["chat"]
    partner = await _partner_for_dialog(db, str(chat_data.get("dialogId") or message_data.get("chatId")))
    if partner is None:
        return None
    room = await db.scalar(select(ChatRoom).where(ChatRoom.partner_id == partner.id, ChatRoom.type == "admin"))
    if room is None:
        room = ChatRoom(partner_id=partner.id, type="admin")
        db.add(room)
        await db.flush()

    text = str(message_data.get("text") or "").strip()
    attachment = None
    file_data = _event_file(data)
    dialog_id = str(chat_data.get("dialogId") or message_data.get("chatId"))
    if client is not None and installation is not None and (file_data is not None or not text):
        file_data = await _event_file_from_history(
            client,
            dialog_id=dialog_id,
            remote_id=remote_id,
            event_file=file_data,
        )
    if file_data is not None and client is not None and installation is not None:
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
        "ONIMBOTV2MESSAGEUPDATE": "updated",
        "ONIMBOTV2MESSAGEDELETE": "deleted",
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


async def _retry_unsynced_partner_messages(db: AsyncSession, partner: Partner) -> int:
    room = await db.scalar(select(ChatRoom).where(ChatRoom.partner_id == partner.id, ChatRoom.type == "admin"))
    if room is None:
        return 0
    messages = list(
        (
            await db.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.room_id == room.id,
                    ChatMessage.origin != "bitrix",
                    ChatMessage.bitrix_message_id.is_(None),
                    ChatMessage.bitrix_sync_status.in_(("not_scheduled", "failed")),
                )
                .order_by(ChatMessage.created_at)
            )
        ).all()
    )
    queued = 0
    for message in messages:
        if await schedule_chat_message(db, message, room=room, retry=True):
            queued += 1
    return queued


async def _create_service_chat(
    db: AsyncSession,
    client: Bitrix24Client,
    installation: BitrixInstallation,
    partner: Partner,
    support_user_ids: list[int] | None = None,
) -> bool:
    if support_user_ids is None:
        support_user_ids = await _active_support_user_ids(client)
    if installation.im_bot_id is None or not support_user_ids:
        return False
    result = await client.call(
        "imbot.v2.Chat.add",
        {
            "botId": installation.im_bot_id,
            "fields": {
                "title": partner_chat_title(partner),
                "description": partner_chat_description(partner),
                "color": "azure",
                "userIds": support_user_ids,
            },
        },
    )
    chat = result.get("chat") if isinstance(result, dict) else None
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if not isinstance(chat_id, int) or isinstance(chat_id, bool):
        raise Bitrix24Error("INVALID_RESPONSE", "Service chat creation returned no chat ID")

    previous_dialog_id = partner.bitrix_chat_id
    partner.bitrix_chat_id = normalize_dialog_id(str(chat_id))
    partner.bitrix_chat_bot_joined_at = datetime.now(UTC)
    queued = await _retry_unsynced_partner_messages(db, partner)
    logger.info(
        "bitrix_service_chat_created",
        partner_id=str(partner.id),
        previous_dialog_id=previous_dialog_id,
        dialog_id=partner.bitrix_chat_id,
        retried_messages=queued,
    )
    return True


async def _find_partner_chat(client: Bitrix24Client, partner: Partner) -> int | None:
    title = partner_chat_title(partner)
    marker = f"partner_cabinet:{partner.id}"
    result = await client.call(
        "im.search.chat.list",
        {"FIND": title, "OFFSET": 0, "LIMIT": 50},
    )
    if not isinstance(result, list):
        return None
    for item in result:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() != title:
            continue
        if marker not in str(item.get("description") or ""):
            continue
        chat_id = _chat_id_from_result(item)
        if chat_id is not None:
            return chat_id
    return None


async def ensure_partner_chats(
    db: AsyncSession,
    client: Bitrix24Client,
    installation: BitrixInstallation,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Create and bind one internal Bitrix chat for every eligible active partner."""
    partners = list(
        (
            await db.scalars(
                select(Partner)
                .where(
                    Partner.status == "active",
                    Partner.deleted_at.is_(None),
                    Partner.bitrix_chat_id.is_(None),
                )
                .order_by(Partner.created_at, Partner.id)
            )
        ).all()
    )
    excluded = 0
    eligible: list[Partner] = []
    for partner in partners:
        if partner_chat_is_excluded(partner):
            excluded += 1
        else:
            eligible.append(partner)
    batch_size = limit if limit is not None else settings.BITRIX_CHAT_PROVISION_BATCH_SIZE
    eligible = eligible[: max(0, batch_size)]
    result = {"created": 0, "recovered": 0, "excluded": excluded, "failed": 0}
    if not eligible:
        return result
    if installation.im_bot_id is None:
        logger.warning("bitrix_partner_chat_provisioning_not_configured")
        result["failed"] = len(eligible)
        return result

    support_user_ids: list[int] | None = None
    for partner in eligible:
        try:
            chat_id = await _find_partner_chat(client, partner)
            if chat_id is not None:
                partner.bitrix_chat_id = normalize_dialog_id(str(chat_id))
                partner.bitrix_chat_bot_joined_at = datetime.now(UTC)
                await _retry_unsynced_partner_messages(db, partner)
                result["recovered"] += 1
            else:
                if support_user_ids is None:
                    support_user_ids = await _active_support_user_ids(client)
                if support_user_ids and await _create_service_chat(
                    db,
                    client,
                    installation,
                    partner,
                    support_user_ids,
                ):
                    result["created"] += 1
                else:
                    result["failed"] += 1
        except Bitrix24Error as exc:
            result["failed"] += 1
            logger.warning(
                "bitrix_partner_chat_provision_failed",
                partner_id=str(partner.id),
                error_code=exc.code,
            )
    await db.flush()
    return result


async def ensure_service_bot(db: AsyncSession, client: Bitrix24Client, installation: BitrixInstallation) -> int:
    if installation.im_bot_id is None:
        result = await client.call(
            "imbot.v2.Bot.register",
            {
                "fields": {
                    "code": BOT_CODE,
                    "type": "supervisor",
                    "eventMode": "fetch",
                    "isHidden": False,
                    "properties": {
                        "name": "ЮРИТЕХ Кабинет",
                        "workPosition": "Сервисный участник интеграции",
                        "color": "AZURE",
                    },
                }
            },
        )
        bot = result.get("bot") if isinstance(result, dict) else None
        bot_id = bot.get("id") if isinstance(bot, dict) else None
        if not isinstance(bot_id, int) or isinstance(bot_id, bool):
            raise Bitrix24Error("INVALID_RESPONSE", "Bot registration returned no bot ID")
        installation.im_bot_id = bot_id
        installation.im_bot_event_offset = None
        await db.flush()

    partners = list(
        (
            await db.scalars(
                select(Partner).where(
                    Partner.bitrix_chat_id.is_not(None),
                    Partner.bitrix_chat_bot_joined_at.is_(None),
                )
            )
        ).all()
    )
    joined = 0
    for partner in partners:
        dialog_id = normalize_dialog_id(partner.bitrix_chat_id or "")
        chat_id = dialog_id[4:] if dialog_id.lower().startswith("chat") else dialog_id
        try:
            await client.call(
                "im.chat.user.add",
                {"CHAT_ID": chat_id, "USERS": [installation.im_bot_id], "HIDE_HISTORY": "N"},
            )
        except Bitrix24Error as exc:
            logger.warning(
                "bitrix_chat_bot_join_failed",
                partner_id=str(partner.id),
                error_code=exc.code,
            )
            if exc.code.upper() in {"ACCESS_ERROR", "ACCESS_DENIED"}:
                try:
                    replacement_created = await _create_service_chat(db, client, installation, partner)
                except Bitrix24Error as create_exc:
                    logger.warning(
                        "bitrix_service_chat_create_failed",
                        partner_id=str(partner.id),
                        error_code=create_exc.code,
                    )
                else:
                    if replacement_created:
                        joined += 1
            continue
        partner.bitrix_chat_bot_joined_at = datetime.now(UTC)
        joined += 1
    await db.flush()
    return joined


async def poll_chat_events(db: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    lock_acquired = await db.scalar(select(func.pg_try_advisory_xact_lock(CHAT_POLL_ADVISORY_LOCK_ID)))
    if lock_acquired is not True:
        logger.info("bitrix_chat_poll_skipped_concurrent_run")
        return _empty_poll_result()
    installation = await active_installation(db)
    if installation is None:
        return _empty_poll_result()
    token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, token) as client:
        joined = await ensure_service_bot(db, client, installation)
        provisioning = await ensure_partner_chats(db, client, installation)

        params: dict[str, Any] = {"botId": installation.im_bot_id, "limit": limit}
        if installation.im_bot_event_offset is not None:
            params["offset"] = installation.im_bot_event_offset
        result = await client.call("imbot.v2.Event.get", params)
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
        installation.im_bot_event_offset = next_offset
    await db.commit()
    return {
        "received": len(events),
        "imported": imported,
        "journaled": journaled,
        "joined": joined,
        **provisioning,
    }
