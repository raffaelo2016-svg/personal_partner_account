from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequest
from app.core.time import MOSCOW_TIMEZONE
from app.database import get_db
from app.models.partner import Partner
from app.models.user import User
from app.schemas.settings import (
    ChangePasswordRequest,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
)
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["partner-settings"])


class TimezoneResponse(BaseModel):
    timezone: str
    region: str | None = None


class TimezoneUpdate(BaseModel):
    timezone: str


async def _current_partner(db: AsyncSession, user: User) -> Partner | None:
    if user.role != "partner":
        return None
    return (
        await db.execute(
            select(Partner).where(
                Partner.user_id == user.id,
                Partner.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


@router.get("/timezone", response_model=TimezoneResponse)
async def get_timezone(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner = await _current_partner(db, current_user)
    if partner is not None:
        return TimezoneResponse(
            timezone=partner.timezone or MOSCOW_TIMEZONE,
            region=partner.region,
        )
    return TimezoneResponse(timezone=MOSCOW_TIMEZONE)


@router.put("/timezone", response_model=TimezoneResponse)
async def update_timezone(
    body: TimezoneUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner = await _current_partner(db, current_user)
    if body.timezone != MOSCOW_TIMEZONE:
        raise BadRequest("Часовой пояс кабинета зафиксирован: Москва (МСК, UTC+3)")
    if partner is not None:
        partner.timezone = MOSCOW_TIMEZONE
        await db.commit()
        return TimezoneResponse(timezone=MOSCOW_TIMEZONE, region=partner.region)
    return TimezoneResponse(timezone=MOSCOW_TIMEZONE)


@router.get("/notifications", response_model=NotificationPreferenceRead)
async def get_notification_prefs(
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.get_notification_preferences(db, current_user.id)


@router.put("/notifications", response_model=NotificationPreferenceRead)
async def update_notification_prefs(
    body: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.update_notification_preferences(
        db,
        current_user.id,
        body.model_dump(exclude_unset=True),
    )


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await settings_service.change_password(
        db,
        current_user.id,
        body.current_password,
        body.new_password,
    )
    return {"detail": "Password changed successfully"}
