from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequest, Forbidden, NotFound
from app.integrations.bitrix24.client import Bitrix24Error
from app.models.client import Client
from app.models.partner import Partner
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskStats, TaskUpdate
from app.services.audit import audit_log

logger = structlog.get_logger()
MOSCOW = ZoneInfo("Europe/Moscow")


def _partner_scope(partner_id: str):
    """Explicit ownership takes priority; support client-only rows during upgrades."""
    return and_(
        or_(
            Task.partner_id == partner_id,
            and_(Task.partner_id.is_(None), Task.client.has(Client.partner_id == partner_id)),
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


def _task_to_read(t: Task, client_name: str | None = None, partner_name: str | None = None) -> TaskRead:
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
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[TaskRead], int]:
    base_q = select(Task).options(selectinload(Task.client), selectinload(Task.partner))
    if partner_id:
        base_q = base_q.where(_partner_scope(partner_id))
    if client_id:
        base_q = base_q.where(Task.client_id == client_id)
    if status == "overdue":
        base_q = base_q.where(_overdue_condition())
    elif status == "pending":
        base_q = base_q.where(Task.status.in_(["pending", "overdue"]), ~_overdue_condition())
    elif status == "in_progress":
        base_q = base_q.where(Task.status == "in_progress", ~_overdue_condition())
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
    return [_task_to_read(t) for t in rows], total


async def create_task(
    session: AsyncSession,
    data: TaskCreate,
    user_id: str,
    *,
    partner_id: str | None = None,
) -> TaskRead:
    client = None
    if data.client_id:
        client = await session.get(Client, data.client_id)
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
    partner = await session.get(Partner, owner_id)
    if partner is None or partner.deleted_at is not None:
        raise NotFound("Partner not found")
    deadline = _deadline_updates(data.model_dump(include={"due_date", "due_at"}, exclude_unset=True))
    task = Task(
        partner_id=owner_id,
        client_id=data.client_id,
        title=data.title,
        description=data.description,
        status="pending",
        priority=data.priority,
        assigned_to=data.assigned_to,
        created_by=user_id,
        **deadline,
    )
    session.add(task)
    await session.flush()

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
) -> TaskRead:
    task = await session.get(
        Task,
        task_id,
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

    await session.flush()
    await session.refresh(task)
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
    task = await session.get(Task, task_id, options=[selectinload(Task.client)])
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
    in_progress = (await session.execute(base.where(Task.status == "in_progress", ~overdue_condition))).scalar() or 0
    completed = (await session.execute(base.where(Task.status == "completed"))).scalar() or 0
    overdue = (await session.execute(base.where(overdue_condition))).scalar() or 0
    return TaskStats(
        total=total,
        pending=pending,
        in_progress=in_progress,
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
