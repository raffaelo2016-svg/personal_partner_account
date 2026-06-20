from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.dependencies import require_role
from app.database import get_db
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.transaction import Transaction
from app.schemas.finance import AdminTransactionRead
from app.schemas.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/admin/finance", tags=["admin-finance"])


@router.get("/transactions", response_model=PaginatedResponse[AdminTransactionRead])
async def list_all_transactions(
    status: str | None = Query(None, pattern="^(pending|completed|failed)$"),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    FeeClient = aliased(Client)  # noqa: N806

    items_q = (
        select(
            Transaction.id,
            Transaction.partner_id,
            Transaction.amount,
            Transaction.status,
            Transaction.payment_method,
            Transaction.external_id,
            Transaction.created_at,
            Partner.company_name.label("partner_name"),
            FeeClient.full_name.label("client_name"),
        )
        .join(Partner, Partner.id == Transaction.partner_id)
        .outerjoin(CourtFee, CourtFee.id == Transaction.court_fee_id)
        .outerjoin(FeeClient, FeeClient.id == CourtFee.client_id)
        .order_by(Transaction.created_at.desc())
    )
    count_q = select(func.count()).select_from(Transaction)

    if status:
        items_q = items_q.where(Transaction.status == status)
        count_q = count_q.where(Transaction.status == status)

    items_q = items_q.offset(pagination.offset).limit(pagination.page_size)

    rows = (await db.execute(items_q)).all()
    total = (await db.execute(count_q)).scalar() or 0

    items = [
        AdminTransactionRead(
            id=str(r.id),
            partner_id=str(r.partner_id),
            partner_name=r.partner_name,
            client_name=r.client_name,
            amount=r.amount,
            status=r.status,
            payment_method=r.payment_method,
            external_id=r.external_id,
            created_at=r.created_at,
        )
        for r in rows
    ]
    pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        pages=pages,
        page_size=pagination.page_size,
    )
