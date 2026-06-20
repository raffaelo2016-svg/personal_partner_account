from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.notification_service import (
    get_unread_count,
    list_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=PaginatedResponse[NotificationRead])
async def list_user_notifications(
    is_read: bool | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    items, total = await list_notifications(
        db,
        str(current_user.id),
        is_read=is_read,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        pages=pages,
        page_size=pagination.page_size,
    )


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    count = await get_unread_count(db, str(current_user.id))
    return {"count": count}


@router.put("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    result = await mark_read(db, notification_id, str(current_user.id))
    await db.commit()
    return result


@router.put("/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    count = await mark_all_read(db, str(current_user.id))
    await db.commit()
    return {"marked_read": count}
