from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.partner import Partner
from app.models.task import Task
from app.models.task_workspace import TaskChatState, TaskMessage
from app.models.user import User

logger = structlog.get_logger()

TASK_MESSAGE_ENTITY_TYPE = "task_message"
TASK_MESSAGE_METHOD = "im.message.add"
TASK_CHAT_POLL_ADVISORY_LOCK_ID = 9_172_402
TASK_CHAT_TASK_LIMIT = 25
TASK_CHAT_MESSAGE_LIMIT = 50
TASK_CHAT_RESOLVE_LIMIT = 5
TASK_CHAT_SYSTEM_AUTHOR = "0"
UNSENT_TASK_MESSAGE_STATUSES = ("not_scheduled", "failed")


def task_dialog_id(task: Task) -> str | None:
    value = (task.bitrix_chat_dialog_id or "").strip()
    return value or None


def normalize_chat_dialog(chat_id: Any) -> str | None:
    """Приводит идентификатор чата к виду ``chat<ID>``."""
    if isinstance(chat_id, bool) or chat_id is None:
        return None
    if isinstance(chat_id, int):
        return f"chat{chat_id}" if chat_id > 0 else None
    value = str(chat_id).strip()
    if value.lower().startswith("chat"):
        value = value[4:]
    return f"chat{value}" if value.isdigit() and int(value) > 0 else None


def is_system_message(message: dict[str, Any]) -> bool:
    """Системные события задачи («изменил исполнителя», «начал выполнять»)."""
    author = str(message.get("author_id") or message.get("authorId") or TASK_CHAT_SYSTEM_AUTHOR).strip()
    return author in {"", TASK_CHAT_SYSTEM_AUTHOR}


def chat_user_names(result: Any) -> dict[str, str]:
    users = result.get("users") if isinstance(result, dict) else None
    names: dict[str, str] = {}
    if not isinstance(users, list):
        return names
    for user in users:
        if not isinstance(user, dict):
            continue
        user_id = str(user.get("id") or "").strip()
        name = str(user.get("name") or "").strip()
        if user_id and name:
            names[user_id] = name
    return names


def message_created_at(message: dict[str, Any]) -> datetime:
    raw = message.get("date")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return datetime.now(UTC)


def decorate_task_message(author_label: str, text: str) -> str:
    """Подпись автора в Битрикс24: там все сообщения кабинета идут от одного аккаунта."""
    label = " ".join(author_label.split()).strip()
    body = text.strip()
    return f"{label}: {body}" if label else body


def build_task_message_payload(dialog_id: str, text: str) -> dict[str, Any]:
    return {"DIALOG_ID": dialog_id, "MESSAGE": text, "SYSTEM": "N"}


async def task_message_author_label(db: AsyncSession, user: User, task: Task) -> str:
    """Подпись «кто написал» для сотрудников, которые работают только в Битрикс24."""
    if user.is_admin:
        local_part = user.email.split("@")[0].strip()
        return f"{local_part or 'ЮРИТЕХ'} (ЮРИТЕХ)"
    partner = await db.get(Partner, task.partner_id) if task.partner_id else None
    name = (partner.director_name or partner.company_name).strip() if partner else ""
    return f"{name} (партнёр)" if name else "Партнёр"


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


async def resolve_task_chat_dialog_id(
    db: AsyncSession,
    task: Task,
    *,
    client: Bitrix24Client | None = None,
) -> str | None:
    """Узнаёт у Битрикс24 диалог чата задачи и запоминает его."""
    existing = task_dialog_id(task)
    if existing is not None:
        return existing
    if not task.bitrix_task_id:
        return None
    installation = await active_installation(db)
    if installation is None:
        return None

    async def read(client_: Bitrix24Client) -> str | None:
        result = await client_.call("tasks.task.get", {"taskId": task.bitrix_task_id})
        remote = result.get("task") if isinstance(result, dict) else None
        return normalize_chat_dialog((remote or {}).get("chatId") or (remote or {}).get("CHAT_ID"))

    if client is not None:
        dialog_id = await read(client)
    else:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as temporary:
            dialog_id = await read(temporary)
    if dialog_id is not None:
        task.bitrix_chat_dialog_id = dialog_id
        await db.flush()
    return dialog_id


async def schedule_task_message(
    db: AsyncSession,
    message: TaskMessage,
    task: Task,
    *,
    text_for_bitrix: str,
    retry: bool = False,
) -> bool:
    """Ставит сообщение кабинета в очередь на отправку в чат задачи."""
    if not task.bitrix_task_id:
        message.bitrix_sync_status = "not_scheduled"
        message.bitrix_sync_error_code = "TASK_NOT_SYNCED"
        return False
    dialog_id = task_dialog_id(task)
    if dialog_id is None:
        message.bitrix_sync_status = "not_scheduled"
        message.bitrix_sync_error_code = "TASK_CHAT_NOT_RESOLVED"
        return False
    installation = await active_installation(db)
    if installation is None:
        message.bitrix_sync_status = "not_scheduled"
        message.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND"
        return False

    operation_key = f"task_message:send:{message.id}:v1"
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
        await db.execute(
            insert(BitrixOutboxOperation)
            .values(
                id=uuid.uuid4(),
                member_id=installation.member_id,
                operation_key=operation_key,
                local_entity_type=TASK_MESSAGE_ENTITY_TYPE,
                local_entity_id=message.id,
                bitrix_method=TASK_MESSAGE_METHOD,
                payload=build_task_message_payload(dialog_id, text_for_bitrix),
                correlation_id=uuid.uuid4(),
                max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        )

    message.bitrix_sync_status = "pending"
    message.bitrix_sync_error_code = None
    message.bitrix_sync_requested_at = datetime.now(UTC)
    await db.flush()
    return True


async def retry_unsent_task_messages(db: AsyncSession, task: Task) -> int:
    """Досылает сообщения кабинета, которые ждали привязки чата задачи."""
    if task_dialog_id(task) is None:
        return 0
    messages = list(
        (
            await db.scalars(
                select(TaskMessage)
                .where(
                    TaskMessage.task_id == task.id,
                    TaskMessage.deleted_at.is_(None),
                    TaskMessage.bitrix_message_id.is_(None),
                    TaskMessage.bitrix_sync_status.in_(UNSENT_TASK_MESSAGE_STATUSES),
                    or_(TaskMessage.origin == "cabinet", TaskMessage.origin.is_(None)),
                )
                .order_by(TaskMessage.created_at.asc())
                .limit(50)
            )
        ).all()
    )
    queued = 0
    for message in messages:
        author = await db.get(User, message.author_id) if message.author_id else None
        if author is None:
            continue
        label = await task_message_author_label(db, author, task)
        if await schedule_task_message(
            db,
            message,
            task,
            text_for_bitrix=decorate_task_message(label, message.text),
            retry=True,
        ):
            queued += 1
    return queued


async def execute_task_message(
    client: Bitrix24Client,
    operation: BitrixOutboxOperation,
    *,
    db: AsyncSession | None = None,
) -> Any:
    try:
        return await client.call(operation.bitrix_method, operation.payload)
    except Bitrix24Error as exc:
        if db is None or exc.code.upper() not in {"ACCESS_DENIED", "NO_ACCESS", "ERROR_ACCESS_DENIED"}:
            raise
        message = await db.get(TaskMessage, operation.local_entity_id)
        task = await db.get(Task, message.task_id) if message is not None else None
        if task is None or not await ensure_task_chat_membership(db, task, client=client):
            raise
        return await client.call(operation.bitrix_method, operation.payload)


async def ensure_task_chat_membership(
    db: AsyncSession,
    task: Task,
    *,
    client: Bitrix24Client | None = None,
) -> bool:
    """Добавляет аккаунт интеграции в чат задачи, если его там ещё нет."""
    dialog_id = task_dialog_id(task)
    if dialog_id is None or not dialog_id[4:].isdigit():
        return False
    installation = await active_installation(db)
    if installation is None:
        return False

    async def add(client_: Bitrix24Client) -> bool:
        user_id = installation.installed_by_user_id
        if not user_id:
            profile = await client_.call("profile", {})
            raw_user_id = profile.get("ID") if isinstance(profile, dict) else None
            user_id = int(raw_user_id) if str(raw_user_id or "").isdigit() else None
            if not user_id:
                return False
            installation.installed_by_user_id = user_id
        await client_.call("im.chat.user.add", {"CHAT_ID": int(dialog_id[4:]), "USERS": [user_id]})
        return True

    try:
        if client is not None:
            return await add(client)
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as temporary:
            return await add(temporary)
    except Bitrix24Error as exc:
        logger.warning("bitrix_task_chat_membership_failed", task_id=str(task.id), error_code=exc.code)
        return False


def _result_message_id(result: Any) -> str | None:
    if isinstance(result, bool):
        return None
    if isinstance(result, int):
        return str(result)
    if isinstance(result, str) and result.strip().isdigit():
        return result.strip()
    if isinstance(result, dict):
        for key in ("messageId", "message_id", "id", "ID"):
            value = result.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return str(value)
            if isinstance(value, str) and value.strip().isdigit():
                return value.strip()
    return None


async def complete_task_message_projection(db: AsyncSession, operation: BitrixOutboxOperation) -> None:
    if operation.local_entity_type != TASK_MESSAGE_ENTITY_TYPE:
        return
    message = await db.get(TaskMessage, operation.local_entity_id)
    remote_id = _result_message_id(operation.result_reference)
    if message is None or not remote_id:
        if message is not None:
            message.bitrix_sync_status = "failed"
            message.bitrix_sync_error_code = "REMOTE_ID_MISSING"
        operation.status = "failed"
        operation.error_code = "REMOTE_ID_MISSING"
        operation.completed_at = None
        return
    message.bitrix_message_id = remote_id
    message.bitrix_sync_status = "synced"
    message.bitrix_sync_error_code = None
    message.bitrix_synced_at = datetime.now(UTC)


def _empty_import_result() -> dict[str, int]:
    return {"tasks": 0, "received": 0, "imported": 0, "resolved": 0, "queued": 0, "skipped": 0, "failed": 0}


async def import_task_chat_messages(
    db: AsyncSession,
    *,
    client: Bitrix24Client | None = None,
    task_limit: int = TASK_CHAT_TASK_LIMIT,
    message_limit: int = TASK_CHAT_MESSAGE_LIMIT,
) -> dict[str, int]:
    """Переносит новые сообщения чатов задач из Битрикс24 в кабинет."""
    lock_acquired = await db.scalar(select(func.pg_try_advisory_xact_lock(TASK_CHAT_POLL_ADVISORY_LOCK_ID)))
    if lock_acquired is not True:
        logger.info("bitrix_task_chat_poll_skipped_concurrent_run")
        return _empty_import_result()

    installation = await active_installation(db)
    if installation is None:
        return _empty_import_result()

    result = _empty_import_result()
    if client is not None:
        await _poll_task_chats(db, client, result, task_limit=task_limit, message_limit=message_limit)
    else:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as temporary:
            await _poll_task_chats(db, temporary, result, task_limit=task_limit, message_limit=message_limit)
    await db.commit()
    return result


async def _poll_task_chats(
    db: AsyncSession,
    client: Bitrix24Client,
    result: dict[str, int],
    *,
    task_limit: int,
    message_limit: int,
) -> None:
    await _attach_missing_dialogs(db, client, result)
    tasks = list(
        (
            await db.scalars(
                select(Task)
                .outerjoin(TaskChatState, TaskChatState.task_id == Task.id)
                .where(
                    Task.bitrix_chat_dialog_id.is_not(None),
                    Task.bitrix_task_id.is_not(None),
                )
                .order_by(TaskChatState.last_polled_at.asc().nulls_first())
                .limit(task_limit)
            )
        ).all()
    )
    result["tasks"] = len(tasks)
    now = datetime.now(UTC)
    for task in tasks:
        dialog_id = task_dialog_id(task)
        if dialog_id is None:
            continue
        try:
            payload = await client.call(
                "im.dialog.messages.get",
                {"DIALOG_ID": dialog_id, "LIMIT": message_limit},
            )
        except Bitrix24Error as exc:
            result["failed"] += 1
            logger.warning(
                "bitrix_task_chat_read_failed",
                task_id=str(task.id),
                dialog_id=dialog_id,
                error_code=exc.code,
            )
            continue

        messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(messages, list):
            result["failed"] += 1
            continue
        result["received"] += len(messages)
        await _import_messages(db, task, payload, messages, result, now=now)
        await _mark_task_polled(db, task.id, now)
        await db.flush()


async def _mark_task_polled(db: AsyncSession, task_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        insert(TaskChatState)
        .values(task_id=task_id, last_polled_at=now)
        .on_conflict_do_update(index_elements=["task_id"], set_={"last_polled_at": now})
    )


async def _attach_missing_dialogs(
    db: AsyncSession,
    client: Bitrix24Client,
    result: dict[str, int],
) -> None:
    now = datetime.now(UTC)
    tasks = list(
        (
            await db.scalars(
                select(Task)
                .outerjoin(TaskChatState, TaskChatState.task_id == Task.id)
                .where(
                    Task.bitrix_chat_dialog_id.is_(None),
                    Task.bitrix_task_id.is_not(None),
                )
                .order_by(TaskChatState.last_polled_at.asc().nulls_first())
                .limit(TASK_CHAT_RESOLVE_LIMIT)
            )
        ).all()
    )
    for task in tasks:
        try:
            dialog_id = await resolve_task_chat_dialog_id(db, task, client=client)
        except Bitrix24Error as exc:
            result["failed"] += 1
            logger.warning("bitrix_task_chat_link_failed", task_id=str(task.id), error_code=exc.code)
            await _mark_task_polled(db, task.id, now)
            continue
        await _mark_task_polled(db, task.id, now)
        if dialog_id is None:
            continue
        result["resolved"] += 1
        result["queued"] += await retry_unsent_task_messages(db, task)


async def _import_messages(
    db: AsyncSession,
    task: Task,
    payload: dict[str, Any],
    messages: list[Any],
    result: dict[str, int],
    *,
    now: datetime,
) -> None:
    names = chat_user_names(payload)
    known_ids = {
        str(value)
        for value in (
            await db.scalars(
                select(TaskMessage.bitrix_message_id).where(
                    TaskMessage.task_id == task.id,
                    TaskMessage.bitrix_message_id.is_not(None),
                )
            )
        ).all()
        if value
    }
    for message in reversed(messages):
        if not isinstance(message, dict) or is_system_message(message):
            result["skipped"] += 1
            continue
        remote_id = str(message.get("id") or "").strip()
        text = str(message.get("text") or "").strip()
        if not remote_id or not text or remote_id in known_ids:
            result["skipped"] += 1
            continue
        author_id = str(message.get("author_id") or message.get("authorId") or "").strip() or None
        db.add(
            TaskMessage(
                task_id=task.id,
                author_id=None,
                text=text,
                origin="bitrix",
                bitrix_sync_status="synced",
                bitrix_message_id=remote_id,
                bitrix_author_id=author_id,
                external_author_name=(names.get(author_id) if author_id else None) or "Сотрудник ЮРИТЕХ",
                bitrix_synced_at=now,
                created_at=message_created_at(message),
            )
        )
        known_ids.add(remote_id)
        result["imported"] += 1
