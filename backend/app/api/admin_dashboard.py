from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.dependencies import require_role
from app.database import get_db
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.transaction import Transaction
from app.services.client_service import BEFORE_COURT_STATUSES, IN_COURT_STATUSES

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


def _percent_change(current: int, previous: int) -> int | None:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100)


def _month_starts(last_month: date, count: int = 6) -> list[date]:
    months: list[date] = []
    cursor = last_month.replace(day=1)
    for _ in range(count):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(months))


@router.get("")
async def admin_dashboard(
    date_from: date | None = Query(None),  # noqa: B008
    date_to: date | None = Query(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    # Snapshot-дата для текущих/просроченных долгов: верхняя граница
    # периода или сегодня, если не задана.
    snapshot_date = date_to or date.today()
    # Верхняя граница для фильтра «событий в периоде» — открытая
    # (< upper), чтобы date_to попал в диапазон целиком.
    upper_bound = snapshot_date + timedelta(days=1)
    has_lower = date_from is not None

    def _in_period(col):
        """Условия фильтрации колонки datetime по [date_from, upper_bound)."""
        conds = [col < upper_bound]
        if has_lower:
            conds.append(col >= date_from)
        return and_(*conds)

    period_days = (snapshot_date - date_from).days + 1 if date_from else None
    previous_start = date_from - timedelta(days=period_days) if date_from and period_days else None
    previous_upper = datetime.combine(date_from, time.min) if date_from else None

    def _in_previous_period(col):
        if previous_start is None or previous_upper is None:
            return None
        return and_(col >= previous_start, col < previous_upper)

    # --- partner stats ---
    partner_stats_q = select(
        func.count().label("total"),
        func.count().filter(Partner.status == "active").label("active"),
        func.count().filter(Partner.status == "pending").label("pending"),
    ).where(Partner.deleted_at.is_(None), _in_period(Partner.created_at))
    p_row = (await db.execute(partner_stats_q)).one()

    network_stats_q = select(
        func.count().label("total"),
        func.count().filter(Partner.status == "active").label("active"),
        func.count().filter(Partner.status == "pending").label("pending"),
    ).where(Partner.deleted_at.is_(None), Partner.created_at < upper_bound)
    network_row = (await db.execute(network_stats_q)).one()

    transmitting_partners_q = select(func.count(func.distinct(Client.partner_id))).where(
        Client.deleted_at.is_(None),
        _in_period(Client.created_at),
    )
    transmitting_partners = (await db.execute(transmitting_partners_q)).scalar() or 0

    activated_new_partners_q = (
        select(func.count(func.distinct(Partner.id)))
        .join(Client, Client.partner_id == Partner.id)
        .where(
            Partner.deleted_at.is_(None),
            Client.deleted_at.is_(None),
            _in_period(Partner.created_at),
            _in_period(Client.created_at),
        )
    )
    activated_new_partners = (await db.execute(activated_new_partners_q)).scalar() or 0
    activation_rate = round((activated_new_partners / p_row.total) * 100) if p_row.total else 0

    # --- client stats ---
    # new_debtors теперь = клиенты, созданные в выбранном периоде
    # (раньше было hardcode «за 7 дней»).
    client_stats_q = select(
        func.count().label("total"),
        func.count().label("new"),
        func.count().filter(Client.status.notin_(["documents_collection", "realization"])).label("in_progress"),
        func.count().filter(Client.status == "realization").label("completed"),
    ).where(Client.deleted_at.is_(None), _in_period(Client.created_at))
    c_row = (await db.execute(client_stats_q)).one()

    client_flow_q = select(
        func.count().filter(Client.status.in_(BEFORE_COURT_STATUSES)).label("before_court"),
        func.count().filter(Client.status.in_(IN_COURT_STATUSES)).label("in_court"),
        func.count().filter(Client.status == "realization").label("completed"),
    ).where(Client.deleted_at.is_(None), _in_period(Client.created_at))
    flow_row = (await db.execute(client_flow_q)).one()

    stale_before = datetime.combine(snapshot_date - timedelta(days=14), time.max)
    clients_without_movement_q = select(func.count()).where(
        Client.deleted_at.is_(None),
        Client.status != "realization",
        Client.created_at < upper_bound,
        Client.updated_at < stale_before,
    )
    clients_without_movement = (await db.execute(clients_without_movement_q)).scalar() or 0

    previous_partners = 0
    previous_clients = 0
    previous_transmitting_partners = 0
    declining_partners = 0
    if previous_start is not None:
        previous_condition_partner = _in_previous_period(Partner.created_at)
        previous_condition_client = _in_previous_period(Client.created_at)
        previous_partners_q = select(func.count()).where(
            Partner.deleted_at.is_(None),
            previous_condition_partner,
        )
        previous_clients_q = select(func.count()).where(
            Client.deleted_at.is_(None),
            previous_condition_client,
        )
        previous_transmitting_q = select(func.count(func.distinct(Client.partner_id))).where(
            Client.deleted_at.is_(None),
            previous_condition_client,
        )
        previous_partners = (await db.execute(previous_partners_q)).scalar() or 0
        previous_clients = (await db.execute(previous_clients_q)).scalar() or 0
        previous_transmitting_partners = (await db.execute(previous_transmitting_q)).scalar() or 0

        partner_period_counts_q = (
            select(
                Client.partner_id,
                func.count().filter(_in_period(Client.created_at)).label("current_count"),
                func.count().filter(previous_condition_client).label("previous_count"),
            )
            .where(
                Client.deleted_at.is_(None),
                Client.created_at >= previous_start,
                Client.created_at < upper_bound,
            )
            .group_by(Client.partner_id)
        )
        partner_period_rows = (await db.execute(partner_period_counts_q)).all()
        declining_partners = sum(
            1 for row in partner_period_rows if row.previous_count > 0 and row.current_count * 2 < row.previous_count
        )

    # --- finance stats (новые начисления + оплаты в периоде) ---
    total_cost_q = select(
        func.coalesce(
            func.sum(
                case(
                    (CourtFee.status.in_(["unpaid", "overdue", "paid"]), CourtFee.amount),
                    else_=0,
                )
            ),
            0,
        )
    ).where(CourtFee.deleted_at.is_(None), _in_period(CourtFee.created_at))
    finance_total_cost = (await db.execute(total_cost_q)).scalar() or 0

    paid_q = select(
        func.coalesce(
            func.sum(
                case(
                    (CourtFee.status == "paid", CourtFee.amount),
                    else_=0,
                )
            ),
            0,
        )
    ).where(
        CourtFee.deleted_at.is_(None),
        CourtFee.paid_at.isnot(None),
        _in_period(CourtFee.paid_at),
    )
    finance_paid = (await db.execute(paid_q)).scalar() or 0

    # --- snapshot debt на snapshot_date ---
    overdue_q = select(
        func.coalesce(func.sum(CourtFee.amount), 0),
    ).where(
        CourtFee.deleted_at.is_(None),
        CourtFee.status.in_(["unpaid", "overdue"]),
        CourtFee.due_date < snapshot_date,
    )
    finance_overdue = (await db.execute(overdue_q)).scalar() or 0

    current_q = (
        select(func.coalesce(func.sum(CourtFee.amount), 0))
        .join(Client, Client.id == CourtFee.client_id)
        .where(
            CourtFee.deleted_at.is_(None),
            CourtFee.status.in_(["unpaid", "overdue"]),
            Client.court_procedure_date.isnot(None),
            Client.court_procedure_date <= snapshot_date,
            CourtFee.due_date >= snapshot_date,
        )
    )
    finance_current = (await db.execute(current_q)).scalar() or 0
    collection_rate = round((finance_paid / finance_total_cost) * 100) if finance_total_cost else 0
    total_debt = finance_current + finance_overdue
    overdue_share = round((finance_overdue / total_debt) * 100) if total_debt else 0

    partners_with_overdue_q = select(func.count(func.distinct(CourtFee.partner_id))).where(
        CourtFee.deleted_at.is_(None),
        CourtFee.status.in_(["unpaid", "overdue"]),
        CourtFee.due_date < snapshot_date,
    )
    partners_with_overdue = (await db.execute(partners_with_overdue_q)).scalar() or 0

    first_client_exists = exists(
        select(Client.id).where(
            Client.partner_id == Partner.id,
            Client.deleted_at.is_(None),
            Client.created_at < upper_bound,
        )
    )
    inactive_cutoff = datetime.combine(snapshot_date - timedelta(days=14), time.max)
    partners_without_first_client_q = select(func.count()).where(
        Partner.deleted_at.is_(None),
        Partner.status == "active",
        Partner.created_at < inactive_cutoff,
        Partner.created_at < upper_bound,
        ~first_client_exists,
    )
    partners_without_first_client = (await db.execute(partners_without_first_client_q)).scalar() or 0

    # --- six-month trend for management charts ---
    trend_months = _month_starts(snapshot_date)
    trend_start = trend_months[0]
    partner_month = func.date_trunc("month", Partner.created_at)
    partner_trend_q = (
        select(partner_month.label("month"), func.count().label("partners"))
        .where(
            Partner.deleted_at.is_(None),
            Partner.created_at >= trend_start,
            Partner.created_at < upper_bound,
        )
        .group_by(partner_month)
    )
    client_month = func.date_trunc("month", Client.created_at)
    client_trend_q = (
        select(
            client_month.label("month"),
            func.count().label("clients"),
            func.count(func.distinct(Client.partner_id)).label("active_partners"),
        )
        .where(
            Client.deleted_at.is_(None),
            Client.created_at >= trend_start,
            Client.created_at < upper_bound,
        )
        .group_by(client_month)
    )
    partner_trend_rows = (await db.execute(partner_trend_q)).all()
    client_trend_rows = (await db.execute(client_trend_q)).all()
    partner_trend_map = {row.month.date(): row.partners for row in partner_trend_rows}
    client_trend_map = {
        row.month.date(): {"clients": row.clients, "active_partners": row.active_partners} for row in client_trend_rows
    }
    activity_trend = [
        {
            "month": month.isoformat(),
            "new_partners": partner_trend_map.get(month, 0),
            "active_partners": client_trend_map.get(month, {}).get("active_partners", 0),
            "clients": client_trend_map.get(month, {}).get("clients", 0),
        }
        for month in trend_months
    ]

    # --- top partners ---
    # Включаем партнёров, созданных до верхней границы.
    partner_clients_q = (
        select(
            Partner.id,
            Partner.company_name,
            Partner.status,
            func.count(Client.id).label("clients_count"),
            func.max(Client.created_at).label("last_client_at"),
        )
        .outerjoin(
            Client,
            (Client.partner_id == Partner.id) & Client.deleted_at.is_(None) & _in_period(Client.created_at),
        )
        .where(Partner.deleted_at.is_(None), Partner.created_at < upper_bound)
        .group_by(Partner.id)
    )
    partner_rows = (await db.execute(partner_clients_q)).all()
    partner_ids = [r.id for r in partner_rows]
    partner_map = {r.id: r for r in partner_rows}

    finance_per_partner = {}
    paid_per_partner: dict = {}
    current_per_partner: dict = {}
    if partner_ids:
        # Начисленные fee в периоде (суммарные по партнёру).
        fp_q = (
            select(
                CourtFee.partner_id,
                func.coalesce(func.sum(CourtFee.amount), 0).label("total_cost"),
            )
            .where(
                CourtFee.deleted_at.is_(None),
                CourtFee.partner_id.in_(partner_ids),
                _in_period(CourtFee.created_at),
            )
            .group_by(CourtFee.partner_id)
        )
        for row in (await db.execute(fp_q)).all():
            finance_per_partner[row.partner_id] = row

        # Оплачено в периоде.
        paid_q = (
            select(
                CourtFee.partner_id,
                func.coalesce(func.sum(CourtFee.amount), 0).label("paid"),
            )
            .where(
                CourtFee.deleted_at.is_(None),
                CourtFee.partner_id.in_(partner_ids),
                CourtFee.status == "paid",
                CourtFee.paid_at.isnot(None),
                _in_period(CourtFee.paid_at),
            )
            .group_by(CourtFee.partner_id)
        )
        paid_per_partner = {r.partner_id: r.paid for r in (await db.execute(paid_q)).all()}

        # Snapshot overdue на snapshot_date.
        overdue_pp_q = (
            select(
                CourtFee.partner_id,
                func.coalesce(func.sum(CourtFee.amount), 0).label("overdue"),
            )
            .where(
                CourtFee.deleted_at.is_(None),
                CourtFee.partner_id.in_(partner_ids),
                CourtFee.status.in_(["unpaid", "overdue"]),
                CourtFee.due_date < snapshot_date,
            )
            .group_by(CourtFee.partner_id)
        )
        overdue_per_partner = {r.partner_id: r.overdue for r in (await db.execute(overdue_pp_q)).all()}

        # Snapshot current на snapshot_date.
        fpc_q = (
            select(
                CourtFee.partner_id,
                func.coalesce(func.sum(CourtFee.amount), 0).label("current"),
            )
            .join(Client, Client.id == CourtFee.client_id)
            .where(
                CourtFee.deleted_at.is_(None),
                CourtFee.partner_id.in_(partner_ids),
                CourtFee.status.in_(["unpaid", "overdue"]),
                Client.court_procedure_date.isnot(None),
                Client.court_procedure_date <= snapshot_date,
                CourtFee.due_date >= snapshot_date,
            )
            .group_by(CourtFee.partner_id)
        )
        current_per_partner = {r.partner_id: r.current for r in (await db.execute(fpc_q)).all()}
    else:
        overdue_per_partner = {}

    top_partners = []
    for pid, p_row_data in partner_map.items():
        fp = finance_per_partner.get(pid)
        top_partners.append(
            {
                "id": str(pid),
                "company_name": p_row_data.company_name,
                "status": p_row_data.status,
                "clients_count": p_row_data.clients_count,
                "last_client_at": p_row_data.last_client_at.isoformat() if p_row_data.last_client_at else None,
                "finance_total_cost": fp.total_cost if fp else 0,
                "finance_current_debt": current_per_partner.get(pid, 0),
                "finance_overdue_debt": overdue_per_partner.get(pid, 0),
                "finance_paid": paid_per_partner.get(pid, 0),
            }
        )

    # --- recent transactions (до 10 в периоде) ---
    FeeClient = aliased(Client)  # noqa: N806
    txn_q = (
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
        .where(_in_period(Transaction.created_at))
        .order_by(Transaction.created_at.desc())
        .limit(10)
    )
    txn_rows = (await db.execute(txn_q)).all()
    recent_transactions = [
        {
            "id": str(r.id),
            "partner_id": str(r.partner_id),
            "partner_name": r.partner_name,
            "client_name": r.client_name,
            "amount": r.amount,
            "status": r.status,
            "payment_method": r.payment_method,
            "external_id": r.external_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in txn_rows
    ]

    return {
        "recent_transactions": recent_transactions,
        "main_stats": {
            "partners_count": p_row.total,
            "active_partners": p_row.active,
            "pending_partners": p_row.pending,
            "new_debtors": c_row.new,
            "total_clients": c_row.total,
            "total_partners": network_row.total,
            "total_active_partners": network_row.active,
            "total_pending_partners": network_row.pending,
            "transmitting_partners": transmitting_partners,
            "activated_new_partners": activated_new_partners,
            "activation_rate": activation_rate,
            "clients_per_active_partner": round(c_row.total / transmitting_partners, 1) if transmitting_partners else 0,
        },
        "movement_stats": {
            "in_progress": c_row.in_progress,
            "completed": c_row.completed,
            "rejected": 0,
            "before_court": flow_row.before_court,
            "in_court": flow_row.in_court,
            "without_movement": clients_without_movement,
        },
        "finance_stats": {
            "total_cost": finance_total_cost,
            "current_debt": finance_current,
            "overdue_debt": finance_overdue,
            "paid": finance_paid,
            "collection_rate": collection_rate,
            "overdue_share": overdue_share,
            "partners_with_overdue": partners_with_overdue,
        },
        "comparison_stats": {
            "new_partners_change_pct": _percent_change(p_row.total, previous_partners),
            "active_partners_change_pct": _percent_change(
                transmitting_partners,
                previous_transmitting_partners,
            ),
            "clients_change_pct": _percent_change(c_row.total, previous_clients),
        },
        "risk_stats": {
            "partners_without_first_client": partners_without_first_client,
            "declining_partners": declining_partners,
            "clients_without_movement": clients_without_movement,
            "partners_with_overdue": partners_with_overdue,
        },
        "activity_trend": activity_trend,
        "top_partners": top_partners,
    }
