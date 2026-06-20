import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.core.security import hash_password, verify_password
from app.models.settings import LoginHistory, NotificationPreference, SystemSetting
from app.models.user import User

logger = structlog.get_logger()

DEFAULT_SETTINGS = {
    "system_name": "URITECH Partner Cabinet",
    "language": "ru",
    "timezone": "Europe/Moscow",
}


async def get_all_settings(db: AsyncSession) -> list[SystemSetting]:
    result = await db.execute(select(SystemSetting))
    rows = list(result.scalars().all())
    existing_keys = {r.key for r in rows}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            rows.append(
                SystemSetting(key=key, value=value),
            )
    return rows


async def update_settings(
    db: AsyncSession,
    updates: dict[str, str],
) -> list[SystemSetting]:
    for key, value in updates.items():
        existing = await db.get(SystemSetting, key)
        if existing:
            existing.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    await db.commit()
    logger.info("system_settings_updated", keys=list(updates.keys()))
    return await get_all_settings(db)


async def get_notification_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> NotificationPreference:
    pref = await db.get(NotificationPreference, user_id)
    if not pref:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


async def update_notification_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
    updates: dict,
) -> NotificationPreference:
    pref = await get_notification_preferences(db, user_id)
    changed = []
    for field, value in updates.items():
        if value is not None and hasattr(pref, field):
            setattr(pref, field, value)
            changed.append(field)
    await db.commit()
    await db.refresh(pref)
    if changed:
        logger.info("notification_prefs_updated", user_id=str(user_id), fields=changed)
    return pref


async def change_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
) -> None:
    user = await db.get(User, user_id)
    if not user:
        logger.warning("password_change_failed", user_id=str(user_id), reason="user_not_found")
        raise NotFound("User not found")
    if not verify_password(current_password, user.hashed_password):
        logger.warning("password_change_failed", user_id=str(user_id), reason="wrong_current_password")
        raise BadRequest("Current password is incorrect")
    if len(new_password) < 8:
        logger.warning("password_change_failed", user_id=str(user_id), reason="password_too_short")
        raise BadRequest("New password must be at least 8 characters")
    user.hashed_password = hash_password(new_password)
    await db.commit()
    logger.info("password_changed", user_id=str(user_id))


async def get_login_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[LoginHistory]:
    result = await db.execute(
        select(LoginHistory)
        .where(LoginHistory.user_id == user_id)
        .order_by(LoginHistory.logged_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


async def record_login(
    db: AsyncSession,
    user_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    entry = LoginHistory(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    await db.commit()
