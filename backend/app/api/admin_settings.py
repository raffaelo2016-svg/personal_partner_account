import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.user import User
from app.schemas.settings import (
    ChangePasswordRequest,
    LoginHistoryRead,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    SystemSettingRead,
    SystemSettingUpdate,
)
from app.services import settings_service

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


@router.get("", response_model=list[SystemSettingRead])
async def get_settings(
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.get_all_settings(db)


@router.put("", response_model=list[SystemSettingRead])
async def update_settings(
    body: SystemSettingUpdate,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.update_settings(db, body.settings)


@router.get("/notifications", response_model=NotificationPreferenceRead)
async def get_notification_prefs(
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.get_notification_preferences(
        db,
        current_user.id,
    )


@router.put("/notifications", response_model=NotificationPreferenceRead)
async def update_notification_prefs(
    body: NotificationPreferenceUpdate,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.update_notification_preferences(
        db,
        current_user.id,
        body.model_dump(exclude_unset=True),
    )


@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await settings_service.change_password(
        db,
        current_user.id,
        body.current_password,
        body.new_password,
    )
    return {"detail": "Password changed successfully"}


@router.get("/login-history", response_model=list[LoginHistoryRead])
async def get_login_history(
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await settings_service.get_login_history(db, current_user.id)


@router.post("/backup")
@limiter.limit("2/minute")
async def trigger_backup(
    request: Request,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    logger.info("backup_triggered", admin_id=str(current_user.id))
    return {
        "detail": "Backup triggered",
        "status": "in_progress",
    }
