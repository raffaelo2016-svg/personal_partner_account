from datetime import UTC, date, datetime, time, timedelta

import structlog
from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import AppException, NotFound
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.transaction import Transaction
from app.schemas.finance import (
    CourtFeeRead,
    CourtFeeSummary,
    DebtBanner,
    TransactionRead,
)
from app.services import yookassa_service
from app.services.audit import audit_log

logger = structlog.get_logger()


def _promotion_datetime_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, tzinfo=UTC),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC),
    )


def _fee_to_read(
    fee: CourtFee,
    client_name: str | None = None,
    client_status: str | None = None,
    court_procedure_date: date | None = None,
) -> CourtFeeRead:
    return CourtFeeRead(
        id=str(fee.id),
        client_id=str(fee.client_id),
        partner_id=str(fee.partner_id),
        base_amount=fee.base_amount,
        discount_amount=fee.discount_amount,
        amount=fee.amount,
        status=fee.status,
        due_date=fee.due_date,
        paid_at=fee.paid_at,
        created_at=fee.created_at,
        client_name=client_name,
        client_status=client_status,
        court_procedure_date=court_procedure_date,
    )


async def create_court_fee_for_client(
    session: AsyncSession,
    client: Client,
    partner: Partner,
) -> CourtFee:
    today = date.today()
    due = today + timedelta(days=partner.payment_term_days or 10)

    # Serialise promotion allocation per partner so concurrent client creates
    # cannot consume the same final free slot.
    locked_partner = (
        await session.execute(select(Partner).where(Partner.id == partner.id).with_for_update())
    ).scalar_one()
    promotion_active = bool(
        locked_partner.free_client_limit > 0
        and locked_partner.promotion_start_date
        and locked_partner.promotion_end_date
        and locked_partner.promotion_start_date <= today <= locked_partner.promotion_end_date
    )
    free_clients_used = 0
    if promotion_active:
        assert locked_partner.promotion_start_date is not None
        assert locked_partner.promotion_end_date is not None
        promotion_start_at, promotion_end_at = _promotion_datetime_bounds(
            locked_partner.promotion_start_date,
            locked_partner.promotion_end_date,
        )
        free_clients_used = (
            await session.execute(
                select(func.count(CourtFee.id)).where(
                    CourtFee.partner_id == locked_partner.id,
                    CourtFee.status == "promo_free",
                    CourtFee.created_at >= promotion_start_at,
                    CourtFee.created_at < promotion_end_at,
                    CourtFee.deleted_at.is_(None),
                )
            )
        ).scalar_one()

    base_amount = locked_partner.court_fee_per_client or 1_500_000
    is_promo_free = promotion_active and free_clients_used < locked_partner.free_client_limit

    fee = CourtFee(
        client_id=client.id,
        partner_id=locked_partner.id,
        base_amount=base_amount,
        discount_amount=base_amount if is_promo_free else 0,
        amount=0 if is_promo_free else base_amount,
        status="promo_free" if is_promo_free else "unpaid",
        due_date=due,
    )
    session.add(fee)
    await session.flush()
    audit_log(
        action="create_court_fee",
        target_id=str(fee.id),
        target_type="court_fee",
        details={
            "client_id": str(client.id),
            "base_amount": fee.base_amount,
            "discount_amount": fee.discount_amount,
            "amount": fee.amount,
            "promotion_applied": is_promo_free,
        },
    )
    logger.info(
        "court_fee_created",
        fee_id=str(fee.id),
        client_id=str(client.id),
        promotion_applied=is_promo_free,
    )
    return fee


async def recalculate_due_date(
    session: AsyncSession,
    client: Client,
    partner: Partner,
) -> None:
    """Пересчитать due_date неоплаченных court_fee при изменении court_procedure_date."""
    if not client.court_procedure_date:
        return

    new_due = client.court_procedure_date + timedelta(days=partner.payment_term_days or 10)

    fees_q = select(CourtFee).where(
        CourtFee.client_id == client.id,
        CourtFee.status.in_(["unpaid", "overdue"]),
        CourtFee.deleted_at.is_(None),
    )
    fees = (await session.execute(fees_q)).scalars().all()
    for fee in fees:
        fee.due_date = new_due
    await session.flush()
    logger.info("due_date_recalculated", client_id=str(client.id), new_due=str(new_due))


async def list_court_fees(
    session: AsyncSession,
    partner_id: str | None = None,
    *,
    client_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[CourtFeeRead], int]:
    base = select(CourtFee).where(CourtFee.deleted_at.is_(None))
    today = date.today()
    if partner_id:
        base = base.where(CourtFee.partner_id == partner_id)
    if client_id:
        base = base.where(CourtFee.client_id == client_id)
    if status:
        base = base.where(CourtFee.status == status)
    if category == "paid":
        base = base.where(CourtFee.status == "paid")
    elif category == "unpaid":
        base = base.where(CourtFee.status.in_(["unpaid", "overdue"]))
    elif category == "overdue":
        base = base.where(CourtFee.status.in_(["unpaid", "overdue"]), CourtFee.due_date < today)
    elif category == "promo_free":
        base = base.where(CourtFee.status == "promo_free")
    elif category == "current":
        base = base.join(Client, Client.id == CourtFee.client_id).where(
            CourtFee.status.in_(["unpaid", "overdue"]),
            Client.court_procedure_date.isnot(None),
            Client.court_procedure_date <= today,
            CourtFee.due_date >= today,
        )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    rows = (
        (
            await session.execute(
                base.options(selectinload(CourtFee.client))
                .order_by(CourtFee.due_date.asc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    result = []
    for fee in rows:
        client = fee.client
        name = client.full_name if client else None
        c_status = client.status if client else None
        c_date = client.court_procedure_date if client else None
        result.append(_fee_to_read(fee, name, c_status, c_date))
    return result, total


async def get_court_fee_summary(session: AsyncSession, partner_id: str) -> CourtFeeSummary:
    partner = await session.get(Partner, partner_id)
    fee_per_client = partner.court_fee_per_client if partner else 0
    free_client_limit = partner.free_client_limit if partner else 0
    promotion_start_date = partner.promotion_start_date if partner else None
    promotion_end_date = partner.promotion_end_date if partner else None
    today = date.today()
    now = datetime.now(UTC)

    unpaid_cond = CourtFee.status.in_(["unpaid", "overdue"])
    overdue_cond = unpaid_cond & (CourtFee.due_date < today)
    paid_month_cond = (
        (CourtFee.status == "paid")
        & (extract("month", CourtFee.paid_at) == now.month)
        & (extract("year", CourtFee.paid_at) == now.year)
    )
    promotion_free_cond = CourtFee.status == "promo_free"
    if promotion_start_date and promotion_end_date:
        promotion_start_at, promotion_end_at = _promotion_datetime_bounds(
            promotion_start_date,
            promotion_end_date,
        )
        promotion_free_cond &= CourtFee.created_at >= promotion_start_at
        promotion_free_cond &= CourtFee.created_at < promotion_end_at
    else:
        promotion_free_cond &= CourtFee.id.is_(None)

    # Query 1: aggregates without Client join
    q1 = select(
        func.coalesce(func.sum(case((unpaid_cond, CourtFee.amount), else_=0)), 0).label("total_debt"),
        func.coalesce(func.sum(case((overdue_cond, CourtFee.amount), else_=0)), 0).label("overdue_debt"),
        func.coalesce(func.sum(case((paid_month_cond, CourtFee.amount), else_=0)), 0).label("paid_this_month"),
        func.count().filter(unpaid_cond).label("unpaid_count"),
        func.count().filter(overdue_cond).label("overdue_count"),
        func.count().filter(promotion_free_cond).label("free_clients_used"),
        func.coalesce(
            func.sum(case((promotion_free_cond, CourtFee.discount_amount), else_=0)),
            0,
        ).label("promotion_savings"),
        func.count().label("total_clients"),
    ).where(
        CourtFee.partner_id == partner_id,
        CourtFee.deleted_at.is_(None),
    )
    r1 = (await session.execute(q1)).one()

    # Query 2: current debt/count (needs Client join)
    q2 = (
        select(
            func.coalesce(func.sum(CourtFee.amount), 0).label("current_debt"),
            func.count().label("current_count"),
        )
        .join(Client, Client.id == CourtFee.client_id)
        .where(
            CourtFee.partner_id == partner_id,
            CourtFee.deleted_at.is_(None),
            CourtFee.status.in_(["unpaid", "overdue"]),
            Client.court_procedure_date.isnot(None),
            Client.court_procedure_date <= today,
            CourtFee.due_date >= today,
        )
    )
    r2 = (await session.execute(q2)).one()

    payment_term_days = partner.payment_term_days if partner else 10
    promotion_active = bool(
        free_client_limit > 0
        and promotion_start_date
        and promotion_end_date
        and promotion_start_date <= today <= promotion_end_date
        and r1.free_clients_used < free_client_limit
    )
    promotion_days_remaining = max(0, (promotion_end_date - today).days) if promotion_end_date else 0
    free_clients_remaining = max(0, free_client_limit - r1.free_clients_used) if promotion_active else 0

    return CourtFeeSummary(
        fee_per_client=fee_per_client,
        total_debt=r1.total_debt,
        current_debt=r2.current_debt,
        overdue_debt=r1.overdue_debt,
        paid_this_month=r1.paid_this_month,
        payment_term_days=payment_term_days,
        unpaid_count=r1.unpaid_count,
        current_count=r2.current_count,
        overdue_count=r1.overdue_count,
        total_clients=r1.total_clients,
        free_client_limit=free_client_limit,
        free_clients_used=r1.free_clients_used,
        free_clients_remaining=free_clients_remaining,
        promotion_start_date=promotion_start_date,
        promotion_end_date=promotion_end_date,
        promotion_active=promotion_active,
        promotion_days_remaining=promotion_days_remaining,
        promotion_savings=r1.promotion_savings,
    )


async def get_debt_banner(session: AsyncSession, partner_id: str) -> DebtBanner:
    q = select(
        func.coalesce(
            func.sum(
                case(
                    (CourtFee.status.in_(["unpaid", "overdue"]), CourtFee.amount),
                    else_=0,
                )
            ),
            0,
        ).label("total_debt"),
        func.coalesce(
            func.sum(
                case(
                    (CourtFee.status == "overdue", CourtFee.amount),
                    else_=0,
                )
            ),
            0,
        ).label("overdue"),
        func.min(
            case(
                (CourtFee.status == "unpaid", CourtFee.due_date),
            )
        ).label("next_due"),
    ).where(
        CourtFee.partner_id == partner_id,
        CourtFee.deleted_at.is_(None),
    )
    row = (await session.execute(q)).one()

    days_until = None
    if row.next_due:
        delta = row.next_due - date.today()
        days_until = max(0, delta.days)

    return DebtBanner(
        total_debt=row.total_debt,
        overdue=row.overdue,
        has_debt=row.total_debt > 0,
        days_until_next_payment=days_until,
    )


async def initiate_payment(
    session: AsyncSession,
    partner_id: str,
    court_fee_id: str,
    payment_method: str,
) -> TransactionRead:
    fee = await session.get(CourtFee, court_fee_id)
    if not fee or fee.deleted_at is not None:
        logger.warning("payment_failed", reason="fee_not_found", court_fee_id=court_fee_id)
        raise NotFound("Court fee not found")
    if str(fee.partner_id) != partner_id:
        logger.warning(
            "payment_failed",
            reason="partner_mismatch",
            court_fee_id=court_fee_id,
            partner_id=partner_id,
        )
        raise NotFound("Court fee not found")
    if fee.status == "promo_free" or fee.amount <= 0:
        raise PaymentError("Эти судебные расходы бесплатны по условиям предложения", code="PROMO_FREE_FEE")

    # Idempotency: if fee is already paid, return the existing transaction
    if fee.status == "paid":
        existing_q = (
            select(Transaction)
            .where(
                Transaction.court_fee_id == fee.id,
                Transaction.status == "completed",
            )
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        existing = (await session.execute(existing_q)).scalar_one_or_none()
        if existing:
            logger.info(
                "payment_idempotent_replay",
                court_fee_id=str(fee.id),
                transaction_id=str(existing.id),
            )
            return TransactionRead(
                id=str(existing.id),
                partner_id=str(existing.partner_id),
                court_fee_id=str(existing.court_fee_id) if existing.court_fee_id else None,
                amount=existing.amount,
                status=existing.status,
                payment_method=existing.payment_method,
                external_id=existing.external_id,
                created_at=existing.created_at,
            )

    txn = Transaction(
        partner_id=partner_id,
        court_fee_id=fee.id,
        amount=fee.amount,
        status="completed",
        payment_method=payment_method,
        external_id=f"STUB-{fee.id}",
    )
    session.add(txn)

    fee.status = "paid"
    fee.paid_at = datetime.now(UTC)
    await session.flush()

    audit_log(
        action="payment_completed",
        target_id=str(txn.id),
        target_type="transaction",
        details={"court_fee_id": str(fee.id), "amount": fee.amount},
    )
    logger.info(
        "payment_completed",
        transaction_id=str(txn.id),
        court_fee_id=str(fee.id),
        partner_id=partner_id,
        amount=fee.amount,
        method=payment_method,
    )
    return TransactionRead(
        id=str(txn.id),
        partner_id=str(txn.partner_id),
        court_fee_id=str(txn.court_fee_id) if txn.court_fee_id else None,
        amount=txn.amount,
        status=txn.status,
        payment_method=txn.payment_method,
        external_id=txn.external_id,
        created_at=txn.created_at,
    )


async def list_transactions(
    session: AsyncSession,
    partner_id: str,
    *,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[TransactionRead], int]:
    base = select(Transaction).where(Transaction.partner_id == partner_id)
    count_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    rows = (
        (await session.execute(base.order_by(Transaction.created_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )

    return [
        TransactionRead(
            id=str(t.id),
            partner_id=str(t.partner_id),
            court_fee_id=str(t.court_fee_id) if t.court_fee_id else None,
            amount=t.amount,
            status=t.status,
            payment_method=t.payment_method,
            external_id=t.external_id,
            created_at=t.created_at,
        )
        for t in rows
    ], total


# ── YooKassa integration ───────────────────────────────────────────────


class PaymentError(AppException):
    def __init__(self, detail: str = "Payment error", code: str = "PAYMENT_ERROR"):
        super().__init__(status_code=400, detail=detail, code=code)


async def create_yookassa_payment_for_fees(
    session: AsyncSession,
    partner_id: str,
    fee_ids: list[str] | None,
    debt_type: str = "all",
) -> dict:
    """Создаёт платёж в ЮKassa для указанных court_fee.

    fee_ids — конкретные позиции. Если None — по debt_type:
      'overdue' — только просроченные (due_date < today)
      'current' — текущие (court_procedure_date <= today AND due_date >= today)
      'all'     — все unpaid+overdue
    Возвращает dict {payment_id, confirmation_url, amount_cents}.
    """
    if not yookassa_service.is_configured():
        raise PaymentError("Платежи не настроены", code="PAYMENTS_DISABLED")

    today = date.today()
    base_q = select(CourtFee).where(
        CourtFee.partner_id == partner_id,
        CourtFee.deleted_at.is_(None),
        CourtFee.status.in_(["unpaid", "overdue"]),
    )
    if fee_ids:
        base_q = base_q.where(CourtFee.id.in_(fee_ids))
    elif debt_type == "overdue":
        base_q = base_q.where(CourtFee.due_date < today)
    elif debt_type == "current":
        base_q = base_q.join(Client, Client.id == CourtFee.client_id).where(
            Client.court_procedure_date.isnot(None),
            Client.court_procedure_date <= today,
            CourtFee.due_date >= today,
        )

    fees = (await session.execute(base_q)).scalars().all()

    if not fees:
        raise PaymentError("Нет неоплаченных судебных расходов", code="NO_UNPAID_FEES")
    if fee_ids and len(fees) != len(fee_ids):
        # часть fee принадлежит другому партнёру либо уже paid
        raise PaymentError("Часть позиций недоступна для оплаты", code="INVALID_FEES")

    total_cents = sum(f.amount for f in fees)
    if total_cents <= 0:
        raise PaymentError("Сумма оплаты должна быть больше 0")

    description = (
        f"Оплата судебных расходов: {len(fees)} клиент(ов)" if len(fees) > 1 else "Оплата судебных расходов клиента"
    )
    metadata = {
        "partner_id": str(partner_id),
        "fee_ids": ",".join(str(f.id) for f in fees),
    }

    payment = yookassa_service.create_payment(
        amount_cents=total_cents,
        return_url=settings.YOOKASSA_RETURN_URL,
        description=description,
        metadata=metadata,
    )
    payment_id = payment["id"]

    # На каждую fee создаём pending-Transaction со ссылкой на платёж
    for fee in fees:
        txn = Transaction(
            partner_id=partner_id,
            court_fee_id=fee.id,
            amount=fee.amount,
            status="pending",
            payment_method="yoo_money",
            external_id=payment_id,
        )
        session.add(txn)

    await session.flush()
    audit_log(
        action="payment_initiated",
        target_id=payment_id,
        target_type="yookassa_payment",
        details={"partner_id": str(partner_id), "fee_ids": metadata["fee_ids"], "amount": total_cents},
    )
    logger.info(
        "yookassa_payment_initiated",
        payment_id=payment_id,
        partner_id=str(partner_id),
        fee_count=len(fees),
        amount=total_cents,
    )
    return {
        "payment_id": payment_id,
        "confirmation_url": payment["confirmation_url"],
        "amount_cents": total_cents,
    }


async def handle_yookassa_event(
    session: AsyncSession,
    event: str,
    payment_id: str,
) -> None:
    """Обработать webhook ЮKassa. Идемпотентен."""
    # Перепроверяем платёж напрямую, чтобы исключить подделку payload
    actual = yookassa_service.fetch_payment(payment_id)
    actual_status = actual["status"]

    txns_q = select(Transaction).where(Transaction.external_id == payment_id)
    txns = (await session.execute(txns_q)).scalars().all()

    if not txns:
        logger.warning("yookassa_event_unknown_payment", payment_id=payment_id, event=event)
        return

    if event == "payment.succeeded" and actual_status == "succeeded":
        for txn in txns:
            if txn.status == "completed":
                continue
            txn.status = "completed"
            if txn.court_fee_id:
                fee = await session.get(CourtFee, txn.court_fee_id)
                if fee and fee.status != "paid":
                    fee.status = "paid"
                    fee.paid_at = datetime.now(UTC)
                    audit_log(
                        action="payment_completed",
                        target_id=str(txn.id),
                        target_type="transaction",
                        details={"court_fee_id": str(fee.id), "payment_id": payment_id},
                    )
        await session.flush()
        logger.info("yookassa_payment_succeeded", payment_id=payment_id, txn_count=len(txns))
    elif event in ("payment.canceled", "payment.failed") or actual_status in ("canceled", "failed"):
        for txn in txns:
            if txn.status not in ("pending",):
                continue
            txn.status = "failed"
        await session.flush()
        logger.info("yookassa_payment_failed", payment_id=payment_id, event=event, txn_count=len(txns))
    else:
        logger.info("yookassa_event_ignored", payment_id=payment_id, event=event, status=actual_status)
