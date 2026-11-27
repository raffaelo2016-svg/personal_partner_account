"""Приёмная сторона интеграции «Битрикс24 -> ЛКП».

Здесь живёт вся логика контура из ТЗ «Передача задач из Битрикс24 в ЛКП»:

* шлюз ЮРИТЕХ присылает задачу (``receive_task``);
* партнёр меняет статус в кабинете (``apply_partner_status``);
* шлюз забирает изменения (``list_status_changes``).

Битрикс24 — главная запись о задаче. Кабинет не редактирует название, срок,
описание и адресата: он принимает их как есть и отдаёт обратно только статус.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import BadRequest, NotFound
from app.models.bitrix_sync import BitrixTaskStatusChange
from app.models.client import Client
from app.models.partner import Partner
from app.models.task import Task
from app.models.user import User
from app.schemas.bitrix_task_integration import (
    IncomingTask,
    IntegrationPartner,
    TaskStatusChangeRead,
)
from app.schemas.task import TaskDetailRead
from app.services.audit import audit_log
from app.services.display_names import user_display_name
from app.services.notification_service import create_notification
from app.services.task_service import add_task_event, get_task_detail

logger = structlog.get_logger()
MOSCOW = ZoneInfo("Europe/Moscow")

GATEWAY_ORIGIN = "bitrix_gateway"
CABINET_ORIGIN = "cabinet"

# Статусы контракта <-> статусы кабинета.
LOCAL_BY_EXTERNAL = {
    "new": "pending",
    "in_progress": "in_progress",
    "done": "completed",
    "rejected": "rejected",
}
EXTERNAL_BY_LOCAL = {value: key for key, value in LOCAL_BY_EXTERNAL.items()}

# Коды статусов Битрикса из таблицы раздела 7 ТЗ. Нужны только для журнала:
# применяет статус к задаче шлюз, не кабинет.
BITRIX_STATUS_CODE = {"new": 2, "in_progress": 4, "done": 5, "rejected": 7}

# Действие партнёра -> статус кабинета.
LOCAL_BY_ACTION = {"in_progress": "in_progress", "done": "completed", "rejected": "rejected"}

ALLOWED_TRANSITIONS = {
    "pending": {"in_progress", "completed", "rejected"},
    "in_progress": {"completed", "rejected"},
    "completed": {"in_progress"},
    "rejected": {"in_progress"},
    "overdue": {"in_progress", "completed", "rejected"},
}

NOTIF_NEW_TASK = "task_from_uritech"
NOTIF_TASK_CHANGED = "task_from_uritech_changed"
NOTIF_TASK_REJECTED = "task_from_uritech_rejected"


@dataclass(slots=True)
class ReceiveResult:
    task: Task
    created: bool


class IntegrationError(Exception):
    """Ошибка контракта: код ответа и код из ТЗ."""

    def __init__(self, status_code: int, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def normalize_inn(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


async def resolve_partner(session: AsyncSession, ref: IntegrationPartner) -> Partner:
    """Однозначный адресат задачи.

    Основной ключ — номер карточки партнёра в Битриксе (``bitrix_id``): он
    стабильнее ИНН, которого в карточках часто нет. ИНН остаётся запасным
    ключом. Неоднозначность — не повод угадывать: задача не создаётся,
    шлюз получает явный отказ.
    """
    if ref.bitrix_id:
        partners = list(
            (
                await session.scalars(
                    select(Partner).where(
                        Partner.bitrix_partner_item_id == ref.bitrix_id,
                        Partner.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        if not partners:
            raise IntegrationError(
                404,
                "partner_not_found",
                f"Карточка партнёра {ref.bitrix_id} не привязана ни к одному аккаунту кабинета",
            )
        if len(partners) > 1:
            raise IntegrationError(
                422,
                "partner_ambiguous",
                f"С карточкой {ref.bitrix_id} связано несколько аккаунтов: {', '.join(str(p.id) for p in partners)}",
            )
        partner = partners[0]
        if ref.inn and normalize_inn(partner.inn) != ref.inn:
            raise IntegrationError(
                409,
                "partner_mismatch",
                "Карточка партнёра и ИНН указывают на разных получателей",
            )
        return partner

    if ref.inn:
        partners = list(
            (
                await session.scalars(
                    select(Partner).where(
                        Partner.inn == ref.inn,
                        Partner.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        if not partners:
            raise IntegrationError(404, "partner_not_found", f"Партнёр с ИНН {ref.inn} не найден в кабинете")
        if len(partners) > 1:
            raise IntegrationError(
                422,
                "partner_ambiguous",
                f"С ИНН {ref.inn} связано несколько аккаунтов: {', '.join(str(p.id) for p in partners)}",
            )
        return partners[0]

    raise IntegrationError(400, "invalid_payload", "Не указан ни номер карточки партнёра, ни ИНН")


async def _fallback_creator_id(session: AsyncSession, partner: Partner) -> uuid.UUID:
    creator_id = await session.scalar(
        select(User.id)
        .where(User.role.in_(("admin", "super_admin")), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .limit(1)
    )
    return creator_id or partner.user_id


async def _find_task(session: AsyncSession, bitrix_task_id: int) -> Task | None:
    task = await session.scalar(
        select(Task).where(Task.bitrix_task_id == str(bitrix_task_id), Task.origin == GATEWAY_ORIGIN)
    )
    if task is not None:
        return task
    # Задачу мог успеть завести старый импорт по тегу «ЛКП». Такую строку
    # подхватываем, чтобы у партнёра не появился дубль.
    return await session.scalar(
        select(Task).where(Task.bitrix_task_id == str(bitrix_task_id)).order_by(Task.created_at.asc()).limit(1)
    )


async def _local_client(session: AsyncSession, partner: Partner, deal_id: int | None) -> Client | None:
    if deal_id is None:
        return None
    return await session.scalar(
        select(Client)
        .where(
            Client.partner_id == partner.id,
            Client.bitrix_deal_id == str(deal_id),
            Client.deleted_at.is_(None),
        )
        .limit(1)
    )


def _task_link(task: Task) -> str:
    return f"{settings.BITRIX_INTEGRATION_LINK_BASE.rstrip('/')}/{task.id}"


def _deadline_note(task: Task) -> str:
    if task.due_at is None:
        return ""
    return f" Срок: {task.due_at.astimezone(MOSCOW):%d.%m.%Y %H:%M} МСК."


async def _notify_new_task(session: AsyncSession, task: Task, partner: Partner) -> None:
    await create_notification(
        session,
        user_id=partner.user_id,
        notif_type=NOTIF_NEW_TASK,
        title="Новая задача от ЮРИТЕХ",
        message=f"{task.title}.{_deadline_note(task)}",
        link=_task_link(task),
    )


async def _notify_task_changed(session: AsyncSession, task: Task, partner: Partner) -> None:
    await create_notification(
        session,
        user_id=partner.user_id,
        notif_type=NOTIF_TASK_CHANGED,
        title="Задача от ЮРИТЕХ изменена",
        message=f"{task.title}.{_deadline_note(task)}",
        link=_task_link(task),
    )


async def _notify_partner_rejected(session: AsyncSession, task: Task, partner: Partner) -> None:
    """Об отклонении сообщаем менеджеру: ему нужно перевыпустить задачу."""
    admins = list(
        (
            await session.scalars(
                select(User.id).where(User.role.in_(("admin", "super_admin")), User.is_active.is_(True))
            )
        ).all()
    )
    for admin_id in admins:
        await create_notification(
            session,
            user_id=admin_id,
            notif_type=NOTIF_TASK_REJECTED,
            title="Партнёр отклонил задачу",
            message=f"{task.title}. Партнёр: {partner.company_name}. Причина: {task.reject_reason or '—'}.",
            link=f"/admin/tasks/{task.id}",
        )


async def receive_task(session: AsyncSession, payload: IncomingTask) -> ReceiveResult:
    """Создать или обновить задачу, пришедшую из Битрикса.

    Ключ идемпотентности — ``bitrix_task_id``. Повторная доставка обновляет
    существующую задачу, а не создаёт вторую.
    """
    partner = await resolve_partner(session, payload.partner)
    task = await _find_task(session, payload.bitrix_task_id)
    now = datetime.now(UTC)

    if task is not None and task.partner_id is not None and task.partner_id != partner.id:
        # Та же задача Битрикса уже принадлежит другому партнёру: молча
        # переадресовать её нельзя, это утечка чужого клиента.
        logger.error(
            "bitrix_task_partner_conflict",
            bitrix_task_id=payload.bitrix_task_id,
            task_id=str(task.id),
            local_partner_id=str(task.partner_id),
            incoming_partner_id=str(partner.id),
        )
        raise IntegrationError(
            409,
            "task_partner_conflict",
            "Задача с таким номером уже привязана к другому партнёру",
        )

    if task is not None and task.bitrix_updated_at is not None:
        if payload.updated_at < task.bitrix_updated_at:
            raise IntegrationError(
                409,
                "stale_update",
                "Пришло изменение старше уже сохранённого",
            )
        if payload.updated_at == task.bitrix_updated_at:
            # Тот же срез, что уже применён. Повторная доставка — успех без правок.
            return ReceiveResult(task=task, created=False)

    created = task is None
    if task is None:
        task = Task(
            partner_id=partner.id,
            title=payload.title,
            status="pending",
            priority=payload.priority,
            assigned_to="partner",
            created_by=await _fallback_creator_id(session, partner),
            origin=GATEWAY_ORIGIN,
            bitrix_imported=True,
            bitrix_published=True,
        )
        session.add(task)

    client = await _local_client(session, partner, payload.client.deal_id if payload.client else None)
    previous_status = task.status
    target_status = LOCAL_BY_EXTERNAL[payload.status]
    deadline_changed = task.due_at != payload.deadline

    task.partner_id = partner.id
    task.title = payload.title
    task.description = payload.description
    task.priority = payload.priority
    task.status = target_status
    task.assigned_to = "partner"
    task.origin = GATEWAY_ORIGIN
    task.bitrix_imported = True
    task.bitrix_published = True
    task.bitrix_task_id = str(payload.bitrix_task_id)
    task.bitrix_url = payload.bitrix_url
    task.bitrix_author_name = payload.author.name
    task.bitrix_author_id = payload.author.user_id
    task.bitrix_client_name = payload.client.name if payload.client else None
    task.bitrix_deal_id = str(payload.client.deal_id) if payload.client and payload.client.deal_id else None
    task.bitrix_status = payload.status
    task.bitrix_updated_at = payload.updated_at
    task.bitrix_synced_at = now
    task.bitrix_sync_status = "synced"
    task.bitrix_sync_error_code = None
    task.client_id = client.id if client is not None else None
    task.due_at = payload.deadline
    task.due_date = payload.deadline.astimezone(MOSCOW).date() if payload.deadline else None
    if target_status == "completed":
        # Момент закрытия не сдвигаем при правке названия или срока.
        if previous_status != "completed":
            task.completed_at = now
    else:
        task.completed_at = None
    if not (previous_status == "rejected" and target_status == "rejected"):
        task.reject_reason = None

    if previous_status != target_status or created:
        task.status_changed_at = now
        if target_status == "completed":
            task.completed_at = now

    await session.flush()

    if created:
        await add_task_event(
            session,
            task.id,
            None,
            "created",
            {
                "title": task.title,
                "origin": GATEWAY_ORIGIN,
                "bitrix_task_id": task.bitrix_task_id,
                "author": task.bitrix_author_name,
            },
        )
        await _notify_new_task(session, task, partner)
    elif previous_status != target_status:
        await add_task_event(
            session,
            task.id,
            None,
            "status_changed",
            {
                "from": previous_status,
                "to": target_status,
                "origin": GATEWAY_ORIGIN,
                "bitrix_author": task.bitrix_author_name,
                "actor_name": task.bitrix_author_name,
            },
        )
        await _notify_task_changed(session, task, partner)
    elif deadline_changed:
        await add_task_event(
            session,
            task.id,
            None,
            "deadline_changed",
            {"due_at": task.due_at.isoformat() if task.due_at else None, "origin": GATEWAY_ORIGIN},
        )

    logger.info(
        "bitrix_task_received",
        bitrix_task_id=payload.bitrix_task_id,
        task_id=str(task.id),
        partner_id=str(partner.id),
        status=payload.status,
        created=created,
    )
    audit_log(
        action="bitrix_task_receive",
        target_id=str(task.id),
        target_type="task",
        details={
            "bitrix_task_id": payload.bitrix_task_id,
            "partner_id": str(partner.id),
            "created": created,
            "status": payload.status,
        },
    )
    return ReceiveResult(task=task, created=created)


async def list_status_changes(
    session: AsyncSession,
    *,
    since: datetime,
    limit: int,
) -> tuple[list[TaskStatusChangeRead], datetime]:
    """Изменения статусов со стороны кабинета — для шлюза.

    Читаем только ``origin='cabinet'``: иначе шлюз получил бы эхо своих же
    обновлений и зациклил применение.
    """
    rows = list(
        (
            await session.scalars(
                select(BitrixTaskStatusChange)
                .where(
                    BitrixTaskStatusChange.origin == CABINET_ORIGIN,
                    BitrixTaskStatusChange.changed_at > since,
                )
                .order_by(BitrixTaskStatusChange.changed_at.asc(), BitrixTaskStatusChange.created_at.asc())
                .limit(limit)
            )
        ).all()
    )
    if not rows:
        return [], datetime.now(UTC)

    items = [_to_change_read(row) for row in rows]
    next_since = rows[-1].changed_at
    return items, next_since


def _to_change_read(row: BitrixTaskStatusChange) -> TaskStatusChangeRead:
    return TaskStatusChangeRead(
        bitrix_task_id=int(row.bitrix_task_id),
        lkp_task_id=str(row.task_id),
        status=EXTERNAL_BY_LOCAL.get(row.status, "new"),
        changed_at=row.changed_at,
        author_name=row.author_name,
        reject_reason=row.reject_reason,
    )


def _ensure_transition(task: Task, target_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(task.status)
    if allowed is None or target_status not in allowed:
        raise BadRequest("Такой переход статуса недоступен")


async def apply_partner_status(
    session: AsyncSession,
    task_id: str,
    *,
    action: str,
    reject_reason: str | None,
    user_id: str,
    partner_id: str | None,
) -> TaskDetailRead:
    """Смена статуса партнёром: взять в работу, выполнить или отклонить."""
    user = await session.get(User, uuid.UUID(str(user_id)))
    if user is None or not user.is_active:
        raise NotFound("Пользователь не найден")
    try:
        task_uuid = uuid.UUID(str(task_id))
    except (ValueError, AttributeError):
        raise NotFound("Задача не найдена") from None
    task = await session.get(
        Task,
        task_uuid,
        options=[selectinload(Task.client), selectinload(Task.partner)],
        with_for_update=True,
        populate_existing=True,
    )
    if task is None:
        raise NotFound("Задача не найдена")
    if partner_id is not None and (task.partner_id is None or str(task.partner_id) != partner_id):
        # 404, а не 403: не подтверждаем существование чужой задачи.
        raise NotFound("Задача не найдена")
    if task.origin != GATEWAY_ORIGIN:
        raise BadRequest("Статус этой задачи меняется по обычному сценарию кабинета")
    if action not in LOCAL_BY_ACTION:
        raise BadRequest("Неизвестное действие")

    target_status = LOCAL_BY_ACTION[action]
    if task.status == target_status:
        return await get_task_detail(session, str(task.id), user_id=str(user.id), partner_id=partner_id)

    if target_status == "rejected" and not reject_reason:
        raise BadRequest("Укажите причину отклонения")
    _ensure_transition(task, target_status)

    # Время изменения делаем строго возрастающим: шлюз забирает изменения по
    # «changed_at > since», и два события с одинаковой меткой могли бы
    # потеряться на границе страницы.
    last_changed_at = await session.scalar(select(func.max(BitrixTaskStatusChange.changed_at)))
    now = datetime.now(UTC)
    if last_changed_at is not None:
        last_aware = last_changed_at if last_changed_at.tzinfo else last_changed_at.replace(tzinfo=UTC)
        if now <= last_aware:
            now = last_aware + timedelta(microseconds=1)

    previous_status = task.status
    task.status = target_status
    task.status_changed_at = now
    task.completed_at = now if target_status == "completed" else None
    task.reject_reason = reject_reason if target_status == "rejected" else None
    task.review_requested_at = None
    task.review_requested_by = None

    author_name = user_display_name(user, task.partner)
    session.add(
        BitrixTaskStatusChange(
            task_id=task.id,
            bitrix_task_id=task.bitrix_task_id or "",
            status=target_status,
            changed_at=now,
            author_name=author_name,
            author_user_id=user.id,
            reject_reason=task.reject_reason,
            origin=CABINET_ORIGIN,
        )
    )
    await add_task_event(
        session,
        task.id,
        str(user.id),
        "status_changed",
        {
            "from": previous_status,
            "to": target_status,
            "origin": CABINET_ORIGIN,
            "reject_reason": task.reject_reason,
        },
    )
    if target_status == "rejected" and task.partner is not None:
        await _notify_partner_rejected(session, task, task.partner)

    await session.flush()
    await session.refresh(task, ["updated_at"])
    logger.info(
        "bitrix_task_partner_status",
        task_id=str(task.id),
        from_status=previous_status,
        to_status=target_status,
        actor=author_name,
    )
    audit_log(
        action="bitrix_task_status_change",
        user_id=str(user.id),
        target_id=str(task.id),
        target_type="task",
        details={
            "from": previous_status,
            "to": target_status,
            "reject_reason": task.reject_reason,
            "bitrix_status_code": BITRIX_STATUS_CODE.get(EXTERNAL_BY_LOCAL.get(target_status, "new")),
        },
    )
    return await get_task_detail(session, str(task.id), user_id=str(user.id), partner_id=partner_id)
