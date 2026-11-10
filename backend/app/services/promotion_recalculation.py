"""Apply saved promotion terms to eligible outstanding fees."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.transaction import Transaction


async def apply_promotion_to_open_fees(session: AsyncSession, partner: Partner) -> int:
    """Grant remaining free slots in creation order; preserve paid/existing free fees."""
    if partner.free_client_limit <= 0 or partner.promotion_start_date is None:
        return 0

    moscow = ZoneInfo("Europe/Moscow")
    start = datetime.combine(partner.promotion_start_date, time.min, moscow).astimezone(UTC)
    conditions = [CourtFee.created_at >= start]
    if partner.promotion_end_date is not None:
        end = datetime.combine(partner.promotion_end_date + timedelta(days=1), time.min, moscow).astimezone(UTC)
        conditions.append(CourtFee.created_at < end)

    fees = (
        (
            await session.execute(
                select(CourtFee)
                .where(CourtFee.partner_id == partner.id, CourtFee.deleted_at.is_(None), *conditions)
                .order_by(CourtFee.created_at, CourtFee.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    remaining = max(0, partner.free_client_limit - sum(fee.status == "promo_free" for fee in fees))
    changed = 0
    for fee in fees:
        if remaining == 0:
            break
        if fee.status not in ("unpaid", "overdue") or fee.paid_at is not None:
            continue
        client = await session.get(Client, fee.client_id)
        if client is None or client.deleted_at is not None:
            continue
        payment_in_progress = await session.scalar(
            select(
                exists().where(
                    Transaction.court_fee_id == fee.id,
                    Transaction.status.in_(["pending", "completed"]),
                )
            )
        )
        if payment_in_progress:
            continue
        previous_amount = fee.amount
        fee.discount_amount = fee.base_amount
        fee.amount = 0
        fee.status = "promo_free"
        session.add(
            AuditLog(
                action="apply_promotion_to_existing_fee",
                target_id=str(fee.id),
                target_type="court_fee",
                details={
                    "partner_id": str(partner.id),
                    "client_id": str(fee.client_id),
                    "previous_amount": previous_amount,
                    "amount": 0,
                },
            )
        )
        remaining -= 1
        changed += 1
    await session.flush()
    return changed
