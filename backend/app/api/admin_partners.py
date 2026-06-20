from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.partner import PartnerCreate, PartnerRead, PartnerStats, PartnerUpdate
from app.services.partner_service import (
    create_partner,
    delete_partner,
    get_partner,
    get_partners_stats,
    list_partners,
    update_partner,
)

router = APIRouter(prefix="/admin/partners", tags=["admin-partners"])


@router.get("", response_model=PaginatedResponse[PartnerRead])
async def list_partners_endpoint(
    search: str | None = Query(None, max_length=100),  # noqa: B008
    status: str | None = Query(None),  # noqa: B008
    date_from: datetime | None = Query(None),  # noqa: B008
    date_to: datetime | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    items, total = await list_partners(
        db,
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to,
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


@router.get("/stats", response_model=PartnerStats)
async def partners_stats(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    return await get_partners_stats(db)


@router.get("/{partner_id}", response_model=PartnerRead)
async def get_partner_endpoint(
    partner_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    return await get_partner(db, partner_id)


@router.post("", response_model=PartnerRead, status_code=201)
async def create_partner_endpoint(
    body: PartnerCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    result = await create_partner(db, body)
    await db.commit()
    return result


@router.put("/{partner_id}", response_model=PartnerRead)
async def update_partner_endpoint(
    partner_id: str,
    body: PartnerUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    result = await update_partner(db, partner_id, body)
    await db.commit()
    return result


@router.delete("/{partner_id}", status_code=204)
async def delete_partner_endpoint(
    partner_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    await delete_partner(db, partner_id)
    await db.commit()
