import hashlib
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequest, Forbidden, NotFound
from app.integrations.bitrix24.client import Bitrix24Error
from app.models.client import Client
from app.models.partner import Partner
from app.models.task import Task
from app.models.task_workspace import TaskEvent, TaskFile, TaskMessage, TaskReadState
from app.schemas.task import (
    TaskClientBrief,
    TaskCreate,
    TaskDetailRead,
    TaskEventRead,
    TaskFileRead,
    TaskMessageRead,
    TaskPermissions,
    TaskRead,
    TaskStats,
    TaskUpdate,
)
from app.services.audit import audit_log
from app.services.s3_service import delete_file_async, download_file_async, upload_file_async
from app.validation.files import (
    ALLOWED_EXTENSIONS,
    MIME_BY_EXTENSION,
    file_extension,
    has_valid_signature,
    normalize_mime_type,
)

TASK_FILE_MAX_SIZE_BYTES = 50 * 1024 * 1024
TASK_FILE_EXTENSIONS = ALLOWED_EXTENSIONS | {".xlsx", ".xls", ".heic"}
TASK_FILE_MIME_BY_EXTENSION = {
    **MIME_BY_EXTENSION,
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".heic": "image/heic",
}


def _as_uuid(value: str | uuid.UUID):
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return value


def _task_file_signature_ok(data: bytes, extension: str) -> bool:
    if extension == ".xlsx":
        return data.startswith(b"PK\x03\x04")
    if extension == ".xls":
        return data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension == ".heic":
        return len(data) >= 12 and data[4:8] == b"ftyp"
    return has_valid_signature(data, extension)


logger = structlog.get_logger()
MOSCOW = ZoneInfo("Europe/Moscow")


def _partner_scope(partner_id: str):
    """Explicit ownership takes priority; support client-only rows during upgrades."""
    partner_uuid = _as_uuid(partner_id)
    return and_(
        or_(
            Task.partner_id == partner_uuid,
            and_(Task.partner_id.is_(None), Task.client.has(Client.partner_id == partner_uuid)),
        ),
        ~and_(Task.bitrix_imported.is_(True), Task.bitrix_published.is_(False)),
    )


def _overdue_condition(now: datetime | None = None):
    now = now or datetime.now(UTC)
    return and_(
        Task.status != "completed",
        or_(
            and_(Task.due_at.is_not(None), Task.due_at < now),
            and_(Task.due_at.is_(None), Task.due_date.is_not(None), Task.due_date < now.astimezone(MOSCOW).date()),
        ),
    )


def _effective_status(task: Task, now: datetime | None = None) -> str:
    if task.status == "completed":
        return "completed"
    now = now or datetime.now(UTC)
    deadline = task.due_at
    if deadline is not None:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        overdue = deadline < now
    else:
        overdue = task.due_date is not None and task.due_date < now.astimezone(MOSCOW).date()
    if overdue:
        return "overdue"
    return "pending" if task.status == "overdue" else task.status


def _authorize_partner(task: Task, partner_id: str | None) -> None:
    if partner_id is None:
        return
    if task.bitrix_imported and not task.bitrix_published:
        raise Forbidden("Task is no longer published to the partner cabinet")
    owner_id = task.partner_id
    if owner_id is None and task.client is not None:
        owner_id = task.client.partner_id
    if owner_id is None or str(owner_id) != partner_id:
        raise Forbidden("Access denied")


def _task_to_read(
    t: Task,
    client_name: str | None = None,
    partner_name: str | None = None,
    *,
    files_count: int = 0,
    messages_count: int = 0,
    unread_count: int = 0,
) -> TaskRead:
    # Only inspect eager-loaded relationships; serialization must never trigger async IO.
    client = t.__dict__.get("client")
    partner = t.__dict__.get("partner")
    owner_id = t.partner_id or (client.partner_id if client is not None else None)
    return TaskRead(
        id=str(t.id),
        partner_id=str(owner_id) if owner_id else None,
        partner_name=partner_name or (partner.company_name if partner else None),
        client_id=str(t.client_id) if t.client_id else None,
        title=t.title,
        description=t.description,
        status=_effective_status(t),
        priority=t.priority,
        assigned_to=t.assigned_to,
        created_by=str(t.created_by),
        due_date=t.due_date,
        due_at=t.due_at,
        completed_at=t.completed_at,
        review_requested_at=t.review_requested_at,
        review_requested_by=str(t.review_requested_by) if t.review_requested_by else None,
        files_count=files_count,
        messages_count=messages_count,
        unread_count=unread_count,
        created_at=t.created_at,
        updated_at=t.updated_at,
        client_name=client_name or (client.full_name if client else None),
        bitrix_sync_status=t.bitrix_sync_status,
        bitrix_sync_error_code=t.bitrix_sync_error_code,
        bitrix_task_id=t.bitrix_task_id,
        bitrix_imported=t.bitrix_imported,
        bitrix_published=t.bitrix_published,
        bitrix_sync_requested_at=t.bitrix_sync_requested_at,
        bitrix_synced_at=t.bitrix_synced_at,
    )


async def _task_counts(session: AsyncSession, task_id, user_id: str | None) -> tuple[int, int, int]:
    files_count = int(
        (await session.execute(select(func.count()).select_from(TaskFile).where(TaskFile.task_id == task_id))).scalar()
        or 0
    )
    messages_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(TaskMessage)
                .where(TaskMessage.task_id == task_id, TaskMessage.deleted_at.is_(None))
            )
        ).scalar()
        or 0
    )
    if user_id is None:
        return files_count, messages_count, 0
    read_user_id = _as_uuid(user_id)
    read_state = (
        await session.execute(
            select(TaskReadState).where(
                TaskReadState.task_id == task_id,
                TaskReadState.user_id == read_user_id,
            )
        )
    ).scalar_one_or_none()
    unread_query = (
        select(func.count())
        .select_from(TaskMessage)
        .where(
            TaskMessage.task_id == task_id,
            TaskMessage.author_id != read_user_id,
            TaskMessage.deleted_at.is_(None),
        )
    )
    if read_state is not None:
        unread_query = unread_query.where(TaskMessage.created_at > read_state.last_read_at)
    unread_count = int((await session.execute(unread_query)).scalar() or 0)
    return files_count, messages_count, unread_count


async def _mark_task_read(session: AsyncSession, task_id, user_id: str) -> None:
    read_user_id = _as_uuid(user_id)
    now = datetime.now(UTC)
    values = {
        "id": uuid.uuid4(),
        "task_id": task_id,
        "user_id": read_user_id,
        "last_read_at": now,
    }
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        statement = pg_insert(TaskReadState).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[TaskReadState.user_id, TaskReadState.task_id],
            set_={"last_read_at": statement.excluded.last_read_at},
        )
        await session.execute(statement)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(TaskReadState).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[TaskReadState.user_id, TaskReadState.task_id],
            set_={"last_read_at": statement.excluded.last_read_at},
        )
        await session.execute(statement)
    else:
        state = (
            await session.execute(
                select(TaskReadState).where(
                    TaskReadState.task_id == task_id,
                    TaskReadState.user_id == read_user_id,
                )
            )
        ).scalar_one_or_none()
        if state is None:
            session.add(TaskReadState(**values))
        else:
            state.last_read_at = now
        await session.flush()


async def add_task_event(
    session: AsyncSession,
    task_id,
    actor_id: str | None,
    event_type: str,
    payload: dict | None = None,
) -> None:
    session.add(
        TaskEvent(
            task_id=task_id,
            actor_id=_as_uuid(actor_id) if actor_id else None,
            type=event_type,
            payload=payload or {},
        )
    )
    await session.flush()


async def _load_task_for_user(
    session: AsyncSession,
    task_id: str,
    *,
    partner_id: str | None,
) -> Task:
    task = await session.get(
        Task,
        _as_uuid(task_id),
        options=[selectinload(Task.client), selectinload(Task.partner)],
        populate_existing=True,
    )
    if task is None:
        raise NotFound("Task not found")
    _authorize_partner(task, partner_id)
    return task


def _client_brief(client: Client | None) -> TaskClientBrief | None:
    if client is None:
        return None
    return TaskClientBrief(
        id=str(client.id),
        full_name=client.full_name,
        case_number=client.case_number,
        status=client.status,
        phone=client.phone,
        arbitrage_court=client.arbitrage_court,
    )


def _file_to_read(file: TaskFile, *, user_id: str, is_admin: bool, task_title: str | None = None) -> TaskFileRead:
    uploader_name = file.uploader.email if file.uploader is not None else "Сотрудник"
    return TaskFileRead(
        id=str(file.id),
        task_id=str(file.task_id),
        client_id=str(file.client_id) if file.client_id else None,
        original_name=file.original_name,
        size=file.size,
        mime_type=file.mime_type,
        created_at=file.created_at,
        uploader_id=str(file.uploaded_by),
        uploader_name=uploader_name,
        can_delete=is_admin or str(file.uploaded_by) == user_id,
        download_url=f"/api/v1/tasks/{file.task_id}/files/{file.id}/download",
        task_title=task_title,
    )


def _message_to_read(message: TaskMessage, *, user_id: str) -> TaskMessageRead:
    author = message.author
    return TaskMessageRead(
        id=str(message.id),
        task_id=str(message.task_id),
        author_id=str(message.author_id),
        author_name=(author.email if author is not None else "Участник"),
        author_role=(author.role if author is not None else "partner"),
        text=message.text,
        created_at=message.created_at,
        is_mine=str(message.author_id) == user_id,
    )


def _event_to_read(event: TaskEvent) -> TaskEventRead:
    return TaskEventRead(
        id=str(event.id),
        type=event.type,
        actor_name=(event.actor.email if event.actor is not None else None),
        payload=event.payload or {},
        created_at=event.created_at,
    )


async def get_task_detail(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: str,
    partner_id: str | None,
) -> TaskDetailRead:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    is_admin = partner_id is None
    await _mark_task_read(session, task.id, user_id)
    files = (
        (
            await session.execute(
                select(TaskFile)
                .options(selectinload(TaskFile.uploader))
                .where(TaskFile.task_id == task.id)
                .order_by(TaskFile.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    messages = (
        (
            await session.execute(
                select(TaskMessage)
                .options(selectinload(TaskMessage.author))
                .where(TaskMessage.task_id == task.id, TaskMessage.deleted_at.is_(None))
                .order_by(TaskMessage.created_at.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    events = (
        (
            await session.execute(
                select(TaskEvent)
                .options(selectinload(TaskEvent.actor))
                .where(TaskEvent.task_id == task.id)
                .order_by(TaskEvent.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    files_count, messages_count, unread_count = await _task_counts(session, task.id, user_id)
    base = _task_to_read(
        task,
        task.client.full_name if task.client else None,
        task.partner.company_name if task.partner else None,
        files_count=files_count,
        messages_count=messages_count,
        unread_count=unread_count,
    )
    partner_is_executor = task.assigned_to == "partner"
    can_request_review = (
        not is_admin and partner_is_executor and task.status == "in_progress" and task.review_requested_at is None
    )
    return TaskDetailRead(
        **base.model_dump(),
        client=_client_brief(task.client),
        files=[_file_to_read(f, user_id=user_id, is_admin=is_admin, task_title=task.title) for f in files],
        messages=[_message_to_read(m, user_id=user_id) for m in messages],
        events=[_event_to_read(e) for e in events],
        permissions=TaskPermissions(
            is_admin=is_admin,
            can_edit=is_admin or task.assigned_to != "partner",
            can_upload=True,
            can_request_review=can_request_review,
            can_approve=is_admin and partner_is_executor and task.review_requested_at is not None,
            can_return=is_admin and partner_is_executor and task.review_requested_at is not None,
            can_delete_task=is_admin,
        ),
    )


async def list_task_files(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: str,
    partner_id: str | None,
) -> list[TaskFileRead]:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    files = (
        (
            await session.execute(
                select(TaskFile)
                .options(selectinload(TaskFile.uploader))
                .where(TaskFile.task_id == task.id)
                .order_by(TaskFile.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_file_to_read(f, user_id=user_id, is_admin=partner_id is None, task_title=task.title) for f in files]


async def store_task_file(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: str,
    partner_id: str | None,
    original_name: str,
    mime_type: str | None,
    data: bytes,
) -> TaskFileRead:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    ext = file_extension(original_name)
    if ext not in TASK_FILE_EXTENSIONS:
        from app.core.exceptions import UnsupportedFileType

        raise UnsupportedFileType()
    if len(data) > TASK_FILE_MAX_SIZE_BYTES:
        from app.core.exceptions import FileTooLarge

        raise FileTooLarge()
    normalized_mime = normalize_mime_type(original_name, mime_type) or TASK_FILE_MIME_BY_EXTENSION.get(ext)
    if normalized_mime is None or not _task_file_signature_ok(data, ext):
        from app.core.exceptions import UnsupportedFileType

        raise UnsupportedFileType()
    s3_key = await upload_file_async(data, original_name, normalized_mime)
    file = TaskFile(
        task_id=task.id,
        client_id=task.client_id,
        uploaded_by=_as_uuid(user_id),
        original_name=original_name,
        s3_key=s3_key,
        size=len(data),
        mime_type=normalized_mime,
        content_sha256=hashlib.sha256(data).hexdigest(),
    )
    session.add(file)
    await session.flush()
    await add_task_event(session, task.id, user_id, "file_uploaded", {"file_id": str(file.id), "name": original_name})
    file = (
        await session.execute(select(TaskFile).options(selectinload(TaskFile.uploader)).where(TaskFile.id == file.id))
    ).scalar_one()
    audit_log(action="upload_task_file", user_id=user_id, target_id=str(task.id), target_type="task")
    return _file_to_read(file, user_id=user_id, is_admin=partner_id is None, task_title=task.title)


async def delete_task_file(
    session: AsyncSession,
    task_id: str,
    file_id: str,
    *,
    user_id: str,
    partner_id: str | None,
) -> None:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    file = await session.get(TaskFile, _as_uuid(file_id))
    if file is None or file.task_id != task.id:
        raise NotFound("File not found")
    if partner_id is not None and str(file.uploaded_by) != user_id:
        raise Forbidden("Delete is allowed only for the author or an administrator")
    s3_key = file.s3_key
    await session.delete(file)
    await session.flush()
    await add_task_event(session, task.id, user_id, "file_deleted", {"file_id": file_id, "name": file.original_name})
    try:
        await delete_file_async(s3_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("task_file_s3_delete_failed", key=s3_key, error=str(exc))
    audit_log(action="delete_task_file", user_id=user_id, target_id=str(task.id), target_type="task")


async def download_task_file(
    session: AsyncSession,
    task_id: str,
    file_id: str,
    *,
    partner_id: str | None,
) -> tuple[bytes, str, str]:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    file = await session.get(TaskFile, _as_uuid(file_id))
    if file is None or file.task_id != task.id:
        raise NotFound("File not found")
    return await download_file_async(file.s3_key), file.original_name, file.mime_type


async def list_client_task_files(
    session: AsyncSession,
    client_id: str,
    *,
    user_id: str,
    partner_id: str | None,
) -> list[TaskFileRead]:
    client = await session.get(Client, _as_uuid(client_id))
    if client is None or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id is not None and str(client.partner_id) != partner_id:
        raise Forbidden("Access denied")
    rows = (
        await session.execute(
            select(TaskFile, Task.title)
            .join(Task, Task.id == TaskFile.task_id)
            .options(selectinload(TaskFile.uploader))
            .where(
                TaskFile.client_id == client.id,
                ~and_(Task.bitrix_imported.is_(True), Task.bitrix_published.is_(False)),
            )
            .order_by(TaskFile.created_at.desc())
            .limit(200)
        )
    ).all()
    return [_file_to_read(file, user_id=user_id, is_admin=partner_id is None, task_title=title) for file, title in rows]


async def list_task_messages(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: str,
    partner_id: str | None,
) -> list[TaskMessageRead]:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    await _mark_task_read(session, task.id, user_id)
    messages = (
        (
            await session.execute(
                select(TaskMessage)
                .options(selectinload(TaskMessage.author))
                .where(TaskMessage.task_id == task.id, TaskMessage.deleted_at.is_(None))
                .order_by(TaskMessage.created_at.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_message_to_read(m, user_id=user_id) for m in messages]


async def send_task_message(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: str,
    partner_id: str | None,
    text: str,
) -> TaskMessageRead:
    task = await _load_task_for_user(session, task_id, partner_id=partner_id)
    clean = text.strip()
    if not clean:
        raise BadRequest("Message cannot be empty")
    if len(clean) > 4000:
        raise BadRequest("Message is too long")
    message = TaskMessage(task_id=task.id, author_id=_as_uuid(user_id), text=clean)
    session.add(message)
    await session.flush()
    await _mark_task_read(session, task.id, user_id)
    await session.refresh(task, ["updated_at"])
    message = (
        await session.execute(
            select(TaskMessage).options(selectinload(TaskMessage.author)).where(TaskMessage.id == message.id)
        )
    ).scalar_one()
    return _message_to_read(message, user_id=user_id)


async def review_task(
    session: AsyncSession,
    task_id: str,
    action: str,
    *,
    user_id: str,
    partner_id: str | None,
) -> TaskDetailRead:
    task = await session.get(
        Task,
        _as_uuid(task_id),
        options=[selectinload(Task.client), selectinload(Task.partner)],
        with_for_update=True,
        populate_existing=True,
    )
    if task is None:
        raise NotFound("Task not found")
    _authorize_partner(task, partner_id)
    is_admin = partner_id is None
    now = datetime.now(UTC)

    if task.assigned_to != "partner":
        raise BadRequest("Review is available only for tasks assigned to a partner")

    if action == "request":
        if is_admin:
            raise Forbidden("Only the partner can send a task to review")
        if task.status == "completed":
            raise BadRequest("Completed task cannot be sent to review")
        if task.status != "in_progress":
            raise BadRequest("Take the task into work before sending it to review")
        if task.review_requested_at is not None:
            raise BadRequest("Task is already on review")
        task.review_requested_at = now
        task.review_requested_by = _as_uuid(user_id)
        await add_task_event(session, task.id, user_id, "review_requested", {})
    elif action == "approve":
        if not is_admin:
            raise Forbidden("Only an administrator can approve a task")
        if task.review_requested_at is None:
            raise BadRequest("Task is not on review")
        if task.bitrix_task_id:
            from app.integrations.bitrix24.tasks import sync_task_status

            try:
                await sync_task_status(session, task, "completed")
            except Bitrix24Error as exc:
                logger.warning("task_review_bitrix_approve_failed", task_id=str(task.id), error_code=exc.code)
                raise BadRequest("Could not update task status in Bitrix24") from exc
        task.status = "completed"
        task.completed_at = now
        task.review_requested_at = None
        task.review_requested_by = None
        await add_task_event(session, task.id, user_id, "review_approved", {})
    elif action == "return":
        if not is_admin:
            raise Forbidden("Only an administrator can return a task")
        if task.review_requested_at is None:
            raise BadRequest("Task is not on review")
        if task.bitrix_task_id:
            from app.integrations.bitrix24.tasks import sync_task_status

            try:
                await sync_task_status(session, task, "in_progress")
            except Bitrix24Error as exc:
                logger.warning("task_review_bitrix_return_failed", task_id=str(task.id), error_code=exc.code)
                raise BadRequest("Could not update task status in Bitrix24") from exc
        task.status = "in_progress"
        task.completed_at = None
        task.review_requested_at = None
        task.review_requested_by = None
        await add_task_event(session, task.id, user_id, "review_returned", {})
    else:
        raise BadRequest("Unknown review action")

    await session.flush()
    await session.refresh(task, ["updated_at"])
    audit_log(
        action=f"task_review_{action}",
        user_id=user_id,
        target_id=str(task.id),
        target_type="task",
    )
    return await get_task_detail(session, str(task.id), user_id=user_id, partner_id=partner_id)


def _deadline_updates(data: dict) -> dict:
    """Keep the old date projection and exact timestamp consistent on partial updates."""
    if "due_at" in data:
        deadline = data["due_at"]
        if deadline is not None:
            data["due_at"] = deadline.astimezone(UTC)
            data["due_date"] = deadline.astimezone(MOSCOW).date()
        elif "due_date" not in data:
            data["due_date"] = None
    elif "due_date" in data:
        # Choosing a date-only deadline also removes a previous precise deadline.
        data["due_at"] = None
    return data


def _task_order():
    return (Task.due_date.asc().nullslast(), Task.due_at.asc().nullslast(), Task.created_at.desc())


async def list_tasks(
    session: AsyncSession,
    *,
    partner_id: str | None = None,
    client_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    search: str | None = None,
    user_id: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[TaskRead], int]:
    base_q = select(Task).options(selectinload(Task.client), selectinload(Task.partner))
    if partner_id:
        base_q = base_q.where(_partner_scope(partner_id))
    if client_id:
        base_q = base_q.where(Task.client_id == _as_uuid(client_id))
    if status == "overdue":
        base_q = base_q.where(_overdue_condition())
    elif status == "pending":
        base_q = base_q.where(Task.status.in_(["pending", "overdue"]), ~_overdue_condition())
    elif status == "in_progress":
        base_q = base_q.where(
            Task.status == "in_progress",
            Task.review_requested_at.is_(None),
            ~_overdue_condition(),
        )
    elif status == "review":
        base_q = base_q.where(Task.review_requested_at.is_not(None), Task.status != "completed")
    elif status:
        base_q = base_q.where(Task.status == status)
    if priority:
        base_q = base_q.where(Task.priority == priority)
    if assigned_to:
        base_q = base_q.where(Task.assigned_to == assigned_to)
    if search:
        base_q = base_q.where(Task.title.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await session.execute(count_q)).scalar() or 0
    rows = (await session.execute(base_q.order_by(*_task_order()).offset(offset).limit(limit))).scalars().all()
    items: list[TaskRead] = []
    for task in rows:
        files_count, messages_count, unread_count = await _task_counts(session, task.id, user_id)
        items.append(
            _task_to_read(
                task,
                task.client.full_name if task.client else None,
                task.partner.company_name if task.partner else None,
                files_count=files_count,
                messages_count=messages_count,
                unread_count=unread_count,
            )
        )
    return items, total


async def create_task(
    session: AsyncSession,
    data: TaskCreate,
    user_id: str,
    *,
    partner_id: str | None = None,
) -> TaskRead:
    client = None
    if data.client_id:
        client = await session.get(Client, _as_uuid(data.client_id))
        if client is None or client.deleted_at is not None:
            raise NotFound("Client not found")
    owner_id = data.partner_id or (str(client.partner_id) if client else partner_id)
    if client and data.partner_id and str(client.partner_id) != data.partner_id:
        raise BadRequest("Client does not belong to the selected partner")
    if not owner_id:
        raise BadRequest("A client or partner is required")
    if partner_id and owner_id != partner_id:
        raise Forbidden("Access denied")
    if partner_id and data.assigned_to == "partner":
        # Партнёр создаёт задачу для ЮРИТЕХ: назначение «партнёру» здесь недопустимо.
        data = data.model_copy(update={"assigned_to": "uritech"})
    owner_uuid = _as_uuid(owner_id)
    partner = await session.get(Partner, owner_uuid)
    if partner is None or partner.deleted_at is not None:
        raise NotFound("Partner not found")
    deadline = _deadline_updates(data.model_dump(include={"due_date", "due_at"}, exclude_unset=True))
    task = Task(
        partner_id=owner_uuid,
        client_id=_as_uuid(data.client_id) if data.client_id else None,
        title=data.title,
        description=data.description,
        status="pending",
        priority=data.priority,
        assigned_to=data.assigned_to,
        created_by=_as_uuid(user_id),
        **deadline,
    )
    session.add(task)
    await session.flush()
    await add_task_event(session, task.id, user_id, "created", {"title": task.title})

    from app.integrations.bitrix24.tasks import schedule_task_creation

    await schedule_task_creation(session, task)
    # Scheduling expires SQL-expression-backed updated_at. Load before serialization.
    await session.refresh(task, ["updated_at"])
    audit_log(action="create_task", target_id=str(task.id), target_type="task")
    logger.info("task_created", task_id=str(task.id), partner_id=owner_id, created_by=user_id, priority=task.priority)
    return _task_to_read(task, client.full_name if client else None, partner.company_name)


async def retry_task_bitrix_sync(
    session: AsyncSession,
    task_id: str,
    *,
    partner_id: str | None = None,
) -> TaskRead:
    task = await session.get(Task, task_id, options=[selectinload(Task.client), selectinload(Task.partner)])
    if task is None:
        raise NotFound("Task not found")
    _authorize_partner(task, partner_id)
    if partner_id and task.assigned_to == "partner":
        raise Forbidden("Only URITECH can manage received tasks")

    from app.integrations.bitrix24.tasks import schedule_task_creation

    await schedule_task_creation(session, task, retry=True)
    await session.flush()
    await session.refresh(task, ["updated_at"])
    return _task_to_read(task)


async def update_task(
    session: AsyncSession,
    task_id: str,
    data: TaskUpdate,
    *,
    partner_id: str | None = None,
    user_id: str | None = None,
) -> TaskRead:
    task = await session.get(
        Task,
        _as_uuid(task_id),
        options=[selectinload(Task.client), selectinload(Task.partner)],
        with_for_update=True,
        populate_existing=True,
    )
    if not task:
        raise NotFound("Task not found")
    _authorize_partner(task, partner_id)

    update_data = data.model_dump(exclude_unset=True)
    if partner_id:
        if task.assigned_to == "partner" and set(update_data) - {"status"}:
            raise Forbidden("Only task status can be changed by the receiving partner")
        if update_data.get("assigned_to") == "partner":
            raise Forbidden("Only URITECH can assign tasks to a partner")
    update_data = _deadline_updates(update_data)
    target_status = update_data.get("status")
    if task.bitrix_imported and "assigned_to" in update_data and update_data["assigned_to"] != task.assigned_to:
        raise BadRequest("Change the recipient of a published task in Bitrix24")
    if task.bitrix_task_id and set(update_data) - {"status"}:
        from app.integrations.bitrix24.tasks import sync_task_fields

        try:
            await sync_task_fields(session, task, update_data)
        except Bitrix24Error as exc:
            logger.warning("task_fields_bitrix_update_failed", task_id=str(task.id), error_code=exc.code)
            raise BadRequest("Could not update task details in Bitrix24") from exc
    if target_status and task.bitrix_task_id and target_status != task.status:
        from app.integrations.bitrix24.tasks import sync_task_status

        try:
            await sync_task_status(session, task, target_status)
        except Bitrix24Error as exc:
            logger.warning("task_status_bitrix_update_failed", task_id=str(task.id), error_code=exc.code)
            raise BadRequest("Could not update task status in Bitrix24") from exc
    for key, value in update_data.items():
        setattr(task, key, value)
    if target_status:
        task.completed_at = datetime.now(UTC) if target_status == "completed" else None
        task.review_requested_at = None
        task.review_requested_by = None

    await session.flush()
    await session.refresh(task)
    if target_status:
        await add_task_event(
            session,
            task.id,
            user_id,
            "status_changed",
            {"to": target_status},
        )
    # Audit JSON uses strings, while ORM writes above retain Python date/datetime values.
    audit_log(
        action="update_task",
        target_id=str(task.id),
        target_type="task",
        details=jsonable_encoder(update_data),
    )
    logger.info("task_updated", task_id=str(task.id), fields=list(update_data), new_status=target_status)
    return _task_to_read(task)


async def delete_task(
    session: AsyncSession,
    task_id: str,
    *,
    partner_id: str | None = None,
) -> None:
    task = await session.get(Task, _as_uuid(task_id), options=[selectinload(Task.client)])
    if not task:
        raise NotFound("Task not found")
    _authorize_partner(task, partner_id)
    if partner_id and task.assigned_to == "partner":
        raise Forbidden("Only URITECH can delete received tasks")
    await session.delete(task)
    await session.flush()
    audit_log(action="delete_task", target_id=task_id, target_type="task")
    logger.info("task_deleted", task_id=task_id)


async def get_task_stats(
    session: AsyncSession,
    *,
    partner_id: str | None = None,
    assigned_to: str | None = None,
) -> TaskStats:
    base = select(func.count()).select_from(Task)
    if partner_id:
        base = base.where(_partner_scope(partner_id))
    if assigned_to:
        base = base.where(Task.assigned_to == assigned_to)
    overdue_condition = _overdue_condition()
    total = (await session.execute(base)).scalar() or 0
    pending = (
        await session.execute(base.where(Task.status.in_(["pending", "overdue"]), ~overdue_condition))
    ).scalar() or 0
    in_progress = (
        await session.execute(
            base.where(
                Task.status == "in_progress",
                Task.review_requested_at.is_(None),
                ~overdue_condition,
            )
        )
    ).scalar() or 0
    review = (
        await session.execute(base.where(Task.review_requested_at.is_not(None), Task.status != "completed"))
    ).scalar() or 0
    completed = (await session.execute(base.where(Task.status == "completed"))).scalar() or 0
    overdue = (await session.execute(base.where(overdue_condition))).scalar() or 0
    return TaskStats(
        total=total,
        pending=pending,
        in_progress=in_progress,
        review=review,
        completed=completed,
        overdue=overdue,
        completion_percent=round((completed / total) * 100, 1) if total else 0.0,
    )


async def get_urgent_tasks(
    session: AsyncSession,
    *,
    partner_id: str | None = None,
    priority: str | None = None,
    limit: int = 5,
) -> list[TaskRead]:
    q = (
        select(Task)
        .options(selectinload(Task.client), selectinload(Task.partner))
        .where(Task.status.in_(["pending", "in_progress", "overdue"]))
        .order_by(*_task_order())
        .limit(limit)
    )
    if partner_id:
        q = q.where(_partner_scope(partner_id))
    if priority:
        q = q.where(Task.priority == priority)
    rows = (await session.execute(q)).scalars().all()
    return [_task_to_read(t) for t in rows]
