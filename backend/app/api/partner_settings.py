from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.settings import SystemSetting
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


class TimezoneUpdate(BaseModel):
    timezone: str


@router.get("/timezone", response_model=TimezoneResponse)
async def get_timezone(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
):
    row = await db.get(SystemSetting, "timezone")
    return TimezoneResponse(timezone=row.value if row else "Europe/Moscow")


@router.put("/timezone", response_model=TimezoneResponse)
async def update_timezone(
    body: TimezoneUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
):
    row = await db.get(SystemSetting, "timezone")
    if row:
        row.value = body.timezone
    else:
        db.add(SystemSetting(key="timezone", value=body.timezone))
    await db.commit()
    return TimezoneResponse(timezone=body.timezone)


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
