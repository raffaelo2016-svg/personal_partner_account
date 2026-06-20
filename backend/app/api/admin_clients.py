from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.schemas.client import ClientRead, ClientUpdate
from app.schemas.finance import CourtFeeRead
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.client_service import get_client, list_clients, update_client
from app.services.finance_service import list_court_fees

router = APIRouter(prefix="/admin/clients", tags=["admin-clients"])


@router.get("", response_model=PaginatedResponse[ClientRead])
async def list_all_clients(
    search: str | None = Query(None, max_length=100),  # noqa: B008
    type: str | None = Query(None),  # noqa: B008
    status: str | None = Query(None),  # noqa: B008
    partner_id: str | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    items, total = await list_clients(
        db,
        partner_id=partner_id,
        search=search,
        client_type=type,
        status=status,
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


@router.get("/{client_id}", response_model=ClientRead)
async def get_any_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    return await get_client(db, client_id)


@router.get("/{client_id}/fees", response_model=PaginatedResponse[CourtFeeRead])
async def client_fees(
    client_id: str,
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    items, total = await list_court_fees(
        db,
        client_id=client_id,
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


@router.put("/{client_id}", response_model=ClientRead)
async def update_any_client(
    client_id: str,
    body: ClientUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    result = await update_client(db, client_id, body)
    await db.commit()
    return result
