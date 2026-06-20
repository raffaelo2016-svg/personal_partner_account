import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.notification import Notification
from app.schemas.notification import NotificationRead

logger = structlog.get_logger()


def _notif_to_read(n: Notification) -> NotificationRead:
    return NotificationRead(
        id=str(n.id),
        user_id=str(n.user_id),
        type=n.type,
        title=n.title,
        message=n.message,
        is_read=n.is_read,
        link=n.link,
        created_at=n.created_at,
    )


async def create_notification(
    session: AsyncSession,
    *,
    user_id: str,
    notif_type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        link=link,
    )
    session.add(notif)
    await session.flush()
    logger.info("notification_created", user_id=user_id, type=notif_type)
    return notif


async def list_notifications(
    session: AsyncSession,
    user_id: str,
    *,
    is_read: bool | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[NotificationRead], int]:
    base = select(Notification).where(Notification.user_id == user_id)
    if is_read is not None:
        base = base.where(Notification.is_read == is_read)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    rows = (
        (await session.execute(base.order_by(Notification.created_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )

    return [_notif_to_read(n) for n in rows], total


async def get_unread_count(session: AsyncSession, user_id: str) -> int:
    q = select(func.count()).where(
        Notification.user_id == user_id,
        Notification.is_read.is_(False),
    )
    return (await session.execute(q)).scalar() or 0


async def mark_read(session: AsyncSession, notification_id: str, user_id: str) -> NotificationRead:
    notif = await session.get(Notification, notification_id)
    if not notif or str(notif.user_id) != user_id:
        raise NotFound("Notification not found")
    notif.is_read = True
    await session.flush()
    return _notif_to_read(notif)


async def mark_all_read(session: AsyncSession, user_id: str) -> int:
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    count = result.rowcount  # type: ignore[attr-defined]
    if count:
        logger.info("notifications_all_marked_read", user_id=user_id, count=count)
    return count
