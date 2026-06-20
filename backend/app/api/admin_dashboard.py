from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.dependencies import require_role
from app.database import get_db
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.transaction import Transaction

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


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

    # --- partner stats ---
    partner_stats_q = select(
        func.count().label("total"),
        func.count().filter(Partner.status == "active").label("active"),
        func.count().filter(Partner.status == "pending").label("pending"),
    ).where(Partner.deleted_at.is_(None), _in_period(Partner.created_at))
    p_row = (await db.execute(partner_stats_q)).one()

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

    # --- top partners ---
    # Включаем партнёров, созданных до верхней границы.
    partner_clients_q = (
        select(
            Partner.id,
            Partner.company_name,
            Partner.status,
            func.count(Client.id).label("clients_count"),
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
        },
        "movement_stats": {
            "in_progress": c_row.in_progress,
            "completed": c_row.completed,
            "rejected": 0,
        },
        "finance_stats": {
            "total_cost": finance_total_cost,
            "current_debt": finance_current,
            "overdue_debt": finance_overdue,
            "paid": finance_paid,
        },
        "top_partners": top_partners,
    }
