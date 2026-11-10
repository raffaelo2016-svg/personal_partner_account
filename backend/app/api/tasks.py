from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.partner import Partner
from app.models.user import User
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.task import TaskCreate, TaskRead, TaskStats, TaskUpdate
from app.services.task_service import (
    create_task,
    delete_task,
    get_task_stats,
    get_urgent_tasks,
    list_tasks,
    retry_task_bitrix_sync,
    update_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _resolve_partner_id(db: AsyncSession, user: User) -> str | None:
    """Return partner_id for partner users, None for admins."""
    if user.role == "admin":
        return None
    row = await db.execute(select(Partner).where(Partner.user_id == user.id, Partner.deleted_at.is_(None)))
    partner = row.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=403, detail="Partner profile not found")
    return str(partner.id)


def _scope_partner(actual: str | None, requested: str | None) -> str | None:
    if actual and requested and actual != requested:
        raise HTTPException(status_code=403, detail="Access denied")
    return actual or requested


@router.get("", response_model=PaginatedResponse[TaskRead])
async def list_tasks_endpoint(
    status: str | None = Query(None),  # noqa: B008
    priority: str | None = Query(None),  # noqa: B008
    assigned_to: str | None = Query(None),  # noqa: B008
    search: str | None = Query(None, max_length=100),  # noqa: B008
    client_id: str | None = Query(None),  # noqa: B008
    partner_id: str | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = _scope_partner(await _resolve_partner_id(db, current_user), partner_id)
    items, total = await list_tasks(
        db,
        partner_id=partner_id,
        client_id=client_id,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        search=search,
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


@router.get("/stats", response_model=TaskStats)
async def tasks_stats_endpoint(
    assigned_to: str | None = Query(None),  # noqa: B008
    partner_id: str | None = Query(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = _scope_partner(await _resolve_partner_id(db, current_user), partner_id)
    return await get_task_stats(db, partner_id=partner_id, assigned_to=assigned_to)


@router.get("/urgent", response_model=list[TaskRead])
async def urgent_tasks_endpoint(
    partner_id: str | None = Query(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = _scope_partner(await _resolve_partner_id(db, current_user), partner_id)
    return await get_urgent_tasks(db, partner_id=partner_id)


@router.post("", response_model=TaskRead, status_code=201)
async def create_task_endpoint(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _resolve_partner_id(db, current_user)
    result = await create_task(db, body, str(current_user.id), partner_id=partner_id)
    await db.commit()
    return result


@router.post("/{task_id}/bitrix/retry", response_model=TaskRead)
async def retry_task_bitrix_endpoint(
    task_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _resolve_partner_id(db, current_user)
    result = await retry_task_bitrix_sync(db, task_id, partner_id=partner_id)
    await db.commit()
    return result


@router.put("/{task_id}", response_model=TaskRead)
async def update_task_endpoint(
    task_id: str,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _resolve_partner_id(db, current_user)
    result = await update_task(db, task_id, body, partner_id=partner_id)
    await db.commit()
    return result


@router.delete("/{task_id}", status_code=204)
async def delete_task_endpoint(
    task_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _resolve_partner_id(db, current_user)
    await delete_task(db, task_id, partner_id=partner_id)
    await db.commit()
