"""Напоминания по задачам, пришедшим из Битрикс24.

ТЗ, раздел 12: за день до срока — напоминание партнёру, при просрочке —
партнёру и менеджеру ЮРИТЕХ. Задача этого модуля — создать уведомление
ровно один раз: повторный запуск не должен дублировать сообщения.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select

from app.celery_app import celery
from app.config import settings

logger = structlog.get_logger()
MOSCOW = ZoneInfo("Europe/Moscow")

GATEWAY_ORIGIN = "bitrix_gateway"
REMINDER_EVENT = "deadline_reminder"
OVERDUE_EVENT = "overdue_notified"
NOTIF_DEADLINE = "task_from_uritech_deadline"
NOTIF_OVERDUE = "task_from_uritech_overdue"


def _format_deadline(value: datetime | None) -> str:
    if value is None:
        return "без срока"
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return f"{aware.astimezone(MOSCOW):%d.%m.%Y %H:%M} МСК"


def _already_notified(session, task_id, event_type: str) -> bool:
    from app.models.task_workspace import TaskEvent

    row = session.scalar(
        select(TaskEvent.id).where(TaskEvent.task_id == task_id, TaskEvent.type == event_type).limit(1)
    )
    return row is not None


def _notify(session, user_ids, *, notif_type: str, title: str, message: str, link: str) -> int:
    from app.models.notification import Notification

    created = 0
    for user_id in user_ids:
        session.add(
            Notification(
                user_id=user_id,
                type=notif_type,
                title=title,
                message=message,
                link=link,
            )
        )
        created += 1
    return created


def _admin_ids(session) -> list:
    from app.models.user import User

    return list(
        session.scalars(select(User.id).where(User.role.in_(("admin", "super_admin")), User.is_active.is_(True))).all()
    )


def _mark(session, task, event_type: str, payload: dict) -> None:
    from app.models.task_workspace import TaskEvent

    session.add(TaskEvent(task_id=task.id, actor_id=None, type=event_type, payload=payload))


@celery.task(autoretry_for=(Exception,), max_retries=3, default_retry_delay=300)
def notify_bitrix_task_deadlines() -> dict[str, int]:
    """Напоминание за сутки и уведомление о просрочке — по одному разу на задачу."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.task import Task

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)
    now = datetime.now(UTC)
    now_naive = now.replace(tzinfo=None)
    soon = now_naive + timedelta(hours=24)
    reminded = overdue = 0

    with Session(engine) as session:
        tasks = list(
            session.scalars(
                select(Task).where(
                    Task.origin == GATEWAY_ORIGIN,
                    Task.assigned_to == "partner",
                    Task.status.in_(("pending", "in_progress")),
                    Task.due_at.is_not(None),
                )
            ).all()
        )
        admins = None
        for task in tasks:
            partner = task.partner
            if partner is None or partner.deleted_at is not None:
                continue
            link = f"/dashboard/tasks/{task.id}"
            deadline = _format_deadline(task.due_at)
            due = task.due_at.replace(tzinfo=None) if task.due_at.tzinfo else task.due_at
            if due < now_naive and not _already_notified(session, task.id, OVERDUE_EVENT):
                if admins is None:
                    admins = _admin_ids(session)
                overdue += _notify(
                    session,
                    [partner.user_id, *admins],
                    notif_type=NOTIF_OVERDUE,
                    title="Задача от ЮРИТЕХ просрочена",
                    message=f"{task.title}. Срок был {deadline}.",
                    link=link,
                )
                _mark(session, task, OVERDUE_EVENT, {"due_at": task.due_at.isoformat()})
            elif now_naive <= due <= soon and not _already_notified(session, task.id, REMINDER_EVENT):
                reminded += _notify(
                    session,
                    [partner.user_id],
                    notif_type=NOTIF_DEADLINE,
                    title="Задача от ЮРИТЕХ: срок завтра",
                    message=f"{task.title}. Срок {deadline}.",
                    link=link,
                )
                _mark(session, task, REMINDER_EVENT, {"due_at": task.due_at.isoformat()})
        session.commit()

    logger.info("bitrix_task_deadlines_checked", reminded=reminded, overdue=overdue, tasks=len(tasks))
    engine.dispose()
    return {"reminded": reminded, "overdue": overdue, "tasks": len(tasks)}
