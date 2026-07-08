from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.user import User
from app.schemas.finance import (
    CourtFeeRead,
    CourtFeeSummary,
    DebtBanner,
    PayRequest,
    TransactionRead,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.client_service import _get_partner_id_for_user
from app.services.finance_service import (
    create_yookassa_payment_for_fees,
    get_court_fee_summary,
    get_debt_banner,
    initiate_payment,
    list_court_fees,
    list_transactions,
)


class CreatePaymentRequest(BaseModel):
    fee_ids: list[str] | None = None  # None — по debt_type
    debt_type: str = "all"  # 'overdue' | 'current' | 'all'


class CreatePaymentResponse(BaseModel):
    payment_id: str
    confirmation_url: str | None
    amount_cents: int


router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/court-fees", response_model=PaginatedResponse[CourtFeeRead])
async def court_fees_list(
    status: str | None = Query(None),  # noqa: B008
    category: str | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    items, total = await list_court_fees(
        db,
        partner_id,
        status=status,
        category=category,
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


@router.get("/court-fees/summary", response_model=CourtFeeSummary)
async def court_fees_summary(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    return await get_court_fee_summary(db, partner_id)


@router.get("/debt-banner", response_model=DebtBanner)
async def debt_banner(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    return await get_debt_banner(db, partner_id)


@router.post("/pay", response_model=TransactionRead, status_code=201)
@limiter.limit("10/minute")
async def pay_court_fee(
    request: Request,
    body: PayRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    result = await initiate_payment(db, partner_id, body.court_fee_id, body.payment_method)
    await db.commit()
    return result


@router.post("/payments", response_model=CreatePaymentResponse, status_code=201)
@limiter.limit("10/minute")
async def create_payment(
    request: Request,
    body: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    result = await create_yookassa_payment_for_fees(db, partner_id, body.fee_ids, body.debt_type)
    await db.commit()
    return result


@router.get("/history", response_model=PaginatedResponse[TransactionRead])
async def transaction_history(
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    items, total = await list_transactions(
        db,
        partner_id,
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
