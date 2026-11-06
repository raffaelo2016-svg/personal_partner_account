from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.partner import (
    PartnerBitrixCollabBinding,
    PartnerClientPauseResponse,
    PartnerCreate,
    PartnerRead,
    PartnerStats,
    PartnerUpdate,
)
from app.services.partner_service import (
    bind_partner_bitrix_collab,
    create_partner,
    delete_partner,
    get_partner,
    get_partners_stats,
    list_partners,
    list_partners_with_client_pause,
    retry_partner_bitrix_sync,
    update_partner,
)

router = APIRouter(prefix="/admin/partners", tags=["admin-partners"])


@router.post("/{partner_id}/bitrix24/retry", response_model=PartnerRead)
async def retry_partner_bitrix_sync_endpoint(
    partner_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    try:
        result = await retry_partner_bitrix_sync(db, partner_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return result


@router.put("/{partner_id}/bitrix24/collab", response_model=PartnerRead)
async def bind_partner_bitrix_collab_endpoint(
    partner_id: str,
    body: PartnerBitrixCollabBinding,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    result = await bind_partner_bitrix_collab(db, partner_id, body)
    await db.commit()
    return result


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


@router.get("/without-clients", response_model=PartnerClientPauseResponse)
async def partners_without_clients(
    mode: str = Query("no_clients", pattern="^(no_clients|stalled)$"),  # noqa: B008
    date_to: datetime | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    """Активные партнёры без клиентского потока («не рабочие» и «затихшие»)."""
    items, total, counts = await list_partners_with_client_pause(
        db,
        mode=mode,
        snapshot_date=date_to.date() if date_to else None,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0
    return PartnerClientPauseResponse(
        items=items,
        total=total,
        page=pagination.page,
        pages=pages,
        page_size=pagination.page_size,
        mode=mode,
        counts=counts,
    )


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
