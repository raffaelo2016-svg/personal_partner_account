from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequest, Forbidden, NotFound
from app.models.client import Client
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskStats, TaskUpdate
from app.services.audit import audit_log

logger = structlog.get_logger()


def _task_to_read(t: Task, client_name: str | None = None) -> TaskRead:
    return TaskRead(
        id=str(t.id),
        client_id=str(t.client_id),
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        assigned_to=t.assigned_to,
        created_by=str(t.created_by),
        due_date=t.due_date,
        completed_at=t.completed_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
        client_name=client_name,
        bitrix_sync_status=t.bitrix_sync_status,
        bitrix_sync_error_code=t.bitrix_sync_error_code,
        bitrix_task_id=t.bitrix_task_id,
        bitrix_sync_requested_at=t.bitrix_sync_requested_at,
        bitrix_synced_at=t.bitrix_synced_at,
    )


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
    base_q = select(Task).options(selectinload(Task.client))
    if partner_id:
        base_q = base_q.join(Client, Task.client_id == Client.id).where(Client.partner_id == partner_id)
    if client_id:
        base_q = base_q.where(Task.client_id == client_id)
    if status:
        base_q = base_q.where(Task.status == status)
    if priority:
        base_q = base_q.where(Task.priority == priority)
    if assigned_to:
        base_q = base_q.where(Task.assigned_to == assigned_to)
    if search:
        pattern = f"%{search}%"
        base_q = base_q.where(Task.title.ilike(pattern))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    rows = (await session.execute(base_q.order_by(Task.due_date.asc()).offset(offset).limit(limit))).scalars().all()

    return [_task_to_read(t, t.client.full_name if t.client else None) for t in rows], total


async def create_task(
    session: AsyncSession,
    data: TaskCreate,
    user_id: str,
    *,
    partner_id: str | None = None,
) -> TaskRead:
    client = await session.get(Client, data.client_id)
    if client is None or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise Forbidden("Access denied")
    task = Task(
        client_id=data.client_id,
        title=data.title,
        description=data.description,
        status="pending",
        priority=data.priority,
        assigned_to=data.assigned_to,
        created_by=user_id,
        due_date=data.due_date,
    )
    session.add(task)
    await session.flush()

    from app.integrations.bitrix24.tasks import schedule_task_creation

    await schedule_task_creation(session, task)
    # Bitrix scheduling flushes sync metadata and expires the SQL-expression-
    # backed updated_at value.  Load it explicitly before serialising the task
    # so the async response does not attempt implicit database IO.
    await session.refresh(task, ["updated_at"])
    audit_log(action="create_task", target_id=str(task.id), target_type="task")
    logger.info(
        "task_created",
        task_id=str(task.id),
        client_id=str(task.client_id),
        created_by=user_id,
        priority=task.priority,
    )
    return _task_to_read(task, client.full_name)


async def retry_task_bitrix_sync(
    session: AsyncSession,
    task_id: str,
    *,
    partner_id: str | None = None,
) -> TaskRead:
    task = await session.get(Task, task_id, options=[selectinload(Task.client)])
    if task is None:
        raise NotFound("Task not found")
    if partner_id and task.client and str(task.client.partner_id) != partner_id:
        raise Forbidden("Access denied")

    from app.integrations.bitrix24.tasks import schedule_task_creation

    await schedule_task_creation(session, task, retry=True)
    await session.flush()
    await session.refresh(task, ["updated_at"])
    return _task_to_read(task, task.client.full_name if task.client else None)


async def update_task(
    session: AsyncSession,
    task_id: str,
    data: TaskUpdate,
    *,
    partner_id: str | None = None,
) -> TaskRead:
    task = await session.get(Task, task_id, options=[selectinload(Task.client)])
    if not task:
        raise NotFound("Task not found")
    if partner_id and task.client and str(task.client.partner_id) != partner_id:
        raise Forbidden("Access denied")

    update_data = data.model_dump(exclude_unset=True, mode="json")
    if "status" in update_data and task.bitrix_task_id:
        raise BadRequest("Task status is managed in Bitrix24")
    for key, value in update_data.items():
        if hasattr(task, key):
            setattr(task, key, value)

    if data.status == "completed" and not task.completed_at:
        task.completed_at = datetime.now(UTC)

    await session.flush()
    await session.refresh(task)
    audit_log(action="update_task", target_id=str(task.id), target_type="task", details=update_data)
    logger.info(
        "task_updated",
        task_id=str(task.id),
        fields=list(update_data.keys()),
        new_status=update_data.get("status"),
    )
    return _task_to_read(task, task.client.full_name if task.client else None)


async def delete_task(
    session: AsyncSession,
    task_id: str,
    *,
    partner_id: str | None = None,
) -> None:
    task = await session.get(Task, task_id, options=[selectinload(Task.client)])
    if not task:
        raise NotFound("Task not found")
    if partner_id and task.client and str(task.client.partner_id) != partner_id:
        raise Forbidden("Access denied")

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
    base = select(func.count())
    if partner_id:
        base = base.select_from(Task).join(Client, Task.client_id == Client.id).where(Client.partner_id == partner_id)
    else:
        base = base.select_from(Task)
    if assigned_to:
        base = base.where(Task.assigned_to == assigned_to)

    today = func.current_date()

    total = (await session.execute(base)).scalar() or 0
    pending = (await session.execute(base.where(Task.status == "pending"))).scalar() or 0
    in_progress = (await session.execute(base.where(Task.status == "in_progress"))).scalar() or 0
    completed = (await session.execute(base.where(Task.status == "completed"))).scalar() or 0
    overdue = (
        await session.execute(base.where(Task.due_date < today, Task.status.notin_(["completed"])))
    ).scalar() or 0

    pct = round((completed / total) * 100, 1) if total > 0 else 0.0

    return TaskStats(
        total=total,
        pending=pending,
        in_progress=in_progress,
        completed=completed,
        overdue=overdue,
        completion_percent=pct,
    )


async def get_urgent_tasks(
    session: AsyncSession,
    *,
    partner_id: str | None = None,
    limit: int = 5,
) -> list[TaskRead]:
    q = (
        select(Task)
        .options(selectinload(Task.client))
        .where(Task.status.in_(["pending", "in_progress", "overdue"]))
        .order_by(Task.due_date.asc())
        .limit(limit)
    )
    if partner_id:
        q = q.join(Client, Task.client_id == Client.id).where(Client.partner_id == partner_id)

    rows = (await session.execute(q)).scalars().all()
    return [_task_to_read(t, t.client.full_name if t.client else None) for t in rows]
