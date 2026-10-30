import calendar
from datetime import date, datetime

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateEmail, NotFound
from app.core.security import hash_password
from app.core.time import moscow_today
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.user import User
from app.schemas.partner import PartnerBitrixCollabBinding, PartnerCreate, PartnerRead, PartnerStats, PartnerUpdate
from app.services.audit import audit_log
from app.services.client_service import COMPLETED_STATUSES

logger = structlog.get_logger()


def add_calendar_month(value: date) -> date:
    """Return the same calendar day next month, clamped to month end."""
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


async def list_partners(
    session: AsyncSession,
    *,
    search: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[PartnerRead], int]:
    base_q = (
        select(Partner).join(User, Partner.user_id == User.id).where(Partner.deleted_at.is_(None), User.role != "admin")
    )

    if search:
        pattern = f"%{search}%"
        base_q = base_q.where(
            Partner.company_name.ilike(pattern) | Partner.director_name.ilike(pattern) | Partner.inn.ilike(pattern)
        )
    if status:
        base_q = base_q.where(Partner.status == status)
    if date_from:
        base_q = base_q.where(Partner.created_at >= date_from)
    if date_to:
        base_q = base_q.where(Partner.created_at <= date_to)

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    rows_q = base_q.order_by(Partner.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(rows_q)
    partners = result.scalars().all()

    partner_ids = [p.id for p in partners]
    user_ids = [p.user_id for p in partners]

    # Batch: users
    user_map: dict[str, str] = {}
    if user_ids:
        u_rows = (await session.execute(select(User.id, User.email).where(User.id.in_(user_ids)))).all()
        user_map = {r.id: r.email for r in u_rows}

    # Batch: client status counts per partner
    counts_map = await _get_client_status_counts_batch(session, partner_ids)

    # Batch: finance per partner
    finance_map = await _get_partner_finance_batch(session, partner_ids)

    items: list[PartnerRead] = []
    for p in partners:
        counts = counts_map.get(p.id, {})
        finance = finance_map.get(p.id, {})
        email = user_map.get(p.user_id)
        items.append(_partner_to_read(p, email=email, **counts, **finance))

    return items, total


async def get_partner(session: AsyncSession, partner_id: str) -> PartnerRead:
    partner = await session.get(Partner, partner_id)
    if not partner or partner.deleted_at is not None:
        raise NotFound("Partner not found")

    counts = await _get_client_status_counts(session, partner.id)
    finance = await _get_partner_finance(session, partner.id)
    user = await session.get(User, partner.user_id)
    email = user.email if user else None

    return _partner_to_read(partner, email=email, **counts, **finance)


async def _get_client_status_counts(session: AsyncSession, partner_id) -> dict:
    """Single-partner version (used by get_partner)."""
    result = await _get_client_status_counts_batch(session, [partner_id])
    return result.get(
        partner_id,
        {
            "clients_count": 0,
            "before_court_count": 0,
            "in_court_count": 0,
            "completed_count": 0,
        },
    )


async def _get_client_status_counts_batch(session: AsyncSession, partner_ids: list) -> dict:
    """Batch: one query for all partners."""
    if not partner_ids:
        return {}
    q = (
        select(
            Client.partner_id,
            func.count().label("clients_count"),
            func.count().filter(Client.type == "before_court").label("before_court_count"),
            func.count().filter(Client.type == "in_court").label("in_court_count"),
            func.count().filter(Client.status.in_(COMPLETED_STATUSES)).label("completed_count"),
        )
        .where(Client.partner_id.in_(partner_ids), Client.deleted_at.is_(None))
        .group_by(Client.partner_id)
    )
    rows = (await session.execute(q)).all()
    return {
        r.partner_id: {
            "clients_count": r.clients_count,
            "before_court_count": r.before_court_count,
            "in_court_count": r.in_court_count,
            "completed_count": r.completed_count,
        }
        for r in rows
    }


async def _get_partner_finance(session: AsyncSession, partner_id) -> dict:
    """Single-partner version (used by get_partner)."""
    result = await _get_partner_finance_batch(session, [partner_id])
    return result.get(
        partner_id,
        {
            "finance_total_cost": 0,
            "finance_current_debt": 0,
            "finance_overdue_debt": 0,
            "finance_paid": 0,
        },
    )


async def _get_partner_finance_batch(session: AsyncSession, partner_ids: list) -> dict:
    """Batch: 2 queries for all partners (one plain, one with Client join)."""
    if not partner_ids:
        return {}
    today = moscow_today()

    # Query 1: total_cost, overdue, paid per partner
    q1 = (
        select(
            CourtFee.partner_id,
            func.coalesce(
                func.sum(
                    case(
                        (CourtFee.status.in_(["unpaid", "overdue"]), CourtFee.amount),
                        else_=0,
                    )
                ),
                0,
            ).label("total_cost"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            CourtFee.status.in_(["unpaid", "overdue"]) & (CourtFee.due_date < today),
                            CourtFee.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("overdue"),
            func.coalesce(
                func.sum(
                    case(
                        (CourtFee.status == "paid", CourtFee.amount),
                        else_=0,
                    )
                ),
                0,
            ).label("paid"),
        )
        .where(CourtFee.partner_id.in_(partner_ids), CourtFee.deleted_at.is_(None))
        .group_by(CourtFee.partner_id)
    )
    result_map: dict = {}
    for r in (await session.execute(q1)).all():
        result_map[r.partner_id] = {
            "finance_total_cost": r.total_cost,
            "finance_overdue_debt": r.overdue,
            "finance_paid": r.paid,
            "finance_current_debt": 0,
        }

    # Query 2: current debt (needs Client join)
    q2 = (
        select(
            CourtFee.partner_id,
            func.coalesce(func.sum(CourtFee.amount), 0).label("current"),
        )
        .join(Client, Client.id == CourtFee.client_id)
        .where(
            CourtFee.partner_id.in_(partner_ids),
            CourtFee.deleted_at.is_(None),
            CourtFee.status.in_(["unpaid", "overdue"]),
            Client.court_procedure_date.isnot(None),
            Client.court_procedure_date <= today,
            CourtFee.due_date >= today,
        )
        .group_by(CourtFee.partner_id)
    )
    for r in (await session.execute(q2)).all():
        if r.partner_id in result_map:
            result_map[r.partner_id]["finance_current_debt"] = r.current

    return result_map


def _partner_to_read(
    partner: Partner,
    *,
    clients_count: int = 0,
    email: str | None = None,
    before_court_count: int = 0,
    in_court_count: int = 0,
    completed_count: int = 0,
    finance_total_cost: int = 0,
    finance_current_debt: int = 0,
    finance_overdue_debt: int = 0,
    finance_paid: int = 0,
) -> PartnerRead:
    return PartnerRead(
        id=str(partner.id),
        user_id=str(partner.user_id),
        email=email,
        partner_type=partner.partner_type or "individual",
        company_name=partner.company_name,
        director_name=partner.director_name,
        inn=partner.inn,
        phone=partner.phone,
        short_name=partner.short_name,
        full_legal_name=partner.full_legal_name,
        legal_address=partner.legal_address,
        postal_address=partner.postal_address,
        kpp=partner.kpp,
        court_fee_per_client=partner.court_fee_per_client,
        payment_term_days=partner.payment_term_days,
        free_client_limit=partner.free_client_limit,
        promotion_start_date=partner.promotion_start_date,
        promotion_end_date=partner.promotion_end_date,
        status=partner.status,
        created_at=partner.created_at,
        updated_at=partner.updated_at,
        bitrix_sync_status=partner.bitrix_sync_status,
        bitrix_sync_error_code=partner.bitrix_sync_error_code,
        bitrix_partner_item_id=partner.bitrix_partner_item_id,
        bitrix_collab_status=partner.bitrix_collab_status,
        bitrix_collab_id=partner.bitrix_collab_id,
        bitrix_chat_id=partner.bitrix_chat_id,
        bitrix_root_folder_id=partner.bitrix_root_folder_id,
        bitrix_sync_requested_at=partner.bitrix_sync_requested_at,
        bitrix_synced_at=partner.bitrix_synced_at,
        clients_count=clients_count,
        before_court_count=before_court_count,
        in_court_count=in_court_count,
        completed_count=completed_count,
        finance_total_cost=finance_total_cost,
        finance_current_debt=finance_current_debt,
        finance_overdue_debt=finance_overdue_debt,
        finance_paid=finance_paid,
    )


async def create_partner(session: AsyncSession, data: PartnerCreate) -> PartnerRead:
    existing = await session.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise DuplicateEmail()

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role="partner",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    free_client_limit = data.free_client_limit or 0
    promotion_start_date = (data.promotion_start_date or moscow_today()) if free_client_limit > 0 else None

    partner = Partner(
        user_id=user.id,
        partner_type=data.partner_type,
        company_name=data.company_name,
        director_name=data.director_name,
        inn=data.inn,
        phone=data.phone,
        short_name=data.short_name,
        full_legal_name=data.full_legal_name,
        legal_address=data.legal_address,
        postal_address=data.postal_address,
        kpp=data.kpp,
        court_fee_per_client=data.court_fee_per_client if data.court_fee_per_client is not None else 1_500_000,
        payment_term_days=data.payment_term_days if data.payment_term_days is not None else 10,
        free_client_limit=free_client_limit,
        promotion_start_date=promotion_start_date,
        promotion_end_date=add_calendar_month(promotion_start_date) if promotion_start_date else None,
        status="active",
    )
    session.add(partner)
    await session.flush()

    from app.services.chat_service import ensure_rooms_for_partner

    await ensure_rooms_for_partner(session, str(partner.id))

    from app.integrations.bitrix24.partners import schedule_partner_creation

    await schedule_partner_creation(session, partner)

    audit_log(action="create_partner", target_id=str(partner.id), target_type="partner")
    logger.info("partner_created", partner_id=str(partner.id), company=data.company_name)

    return _partner_to_read(partner, email=user.email)


async def update_partner(session: AsyncSession, partner_id: str, data: PartnerUpdate) -> PartnerRead:
    partner = await session.get(Partner, partner_id)
    if not partner or partner.deleted_at is not None:
        raise NotFound("Partner not found")

    previous_status = partner.status
    previous_promotion_start_date = partner.promotion_start_date
    previous_promotion_end_date = partner.promotion_end_date
    update_data = data.model_dump(exclude_unset=True)
    court_fee_submitted = "court_fee_per_client" in update_data
    payment_term_submitted = "payment_term_days" in update_data
    for key, value in update_data.items():
        if hasattr(partner, key):
            setattr(partner, key, value if not hasattr(value, "value") else value.value)

    if partner.free_client_limit <= 0:
        partner.free_client_limit = 0
        partner.promotion_start_date = None
        partner.promotion_end_date = None
    elif partner.promotion_start_date is None:
        partner.promotion_start_date = partner.promotion_start_date or moscow_today()
        partner.promotion_end_date = add_calendar_month(partner.promotion_start_date)
    elif (
        "promotion_start_date" in update_data
        and partner.promotion_start_date != previous_promotion_start_date
        and previous_promotion_end_date is not None
    ):
        partner.promotion_end_date = add_calendar_month(partner.promotion_start_date)

    await session.flush()
    if court_fee_submitted or payment_term_submitted:
        from app.services.finance_service import sync_open_court_fees_with_partner_terms

        await sync_open_court_fees_with_partner_terms(
            session,
            partner,
            sync_amount=court_fee_submitted,
            sync_due_date=payment_term_submitted,
        )
    if previous_status != "active" and partner.status == "active":
        from app.integrations.bitrix24.partners import schedule_partner_creation

        await schedule_partner_creation(session, partner)
    audit_log(
        action="update_partner",
        target_id=str(partner.id),
        target_type="partner",
        details=update_data,
    )
    logger.info(
        "partner_updated",
        partner_id=str(partner.id),
        fields=list(update_data.keys()),
        new_status=update_data.get("status"),
    )

    return await get_partner(session, partner_id)


async def retry_partner_bitrix_sync(session: AsyncSession, partner_id: str) -> PartnerRead:
    partner = await session.get(Partner, partner_id)
    if not partner or partner.deleted_at is not None:
        raise NotFound("Partner not found")
    if partner.status != "active":
        raise ValueError("Синхронизация доступна только активному партнёру")
    if partner.bitrix_sync_status == "conflict":
        raise ValueError("Конфликт требует решения администратора")

    from app.integrations.bitrix24.partners import schedule_partner_creation

    queued = await schedule_partner_creation(session, partner, retry=True)
    if not queued and partner.bitrix_sync_status == "not_scheduled":
        raise ValueError("Активная установка Битрикс24 не найдена")
    audit_log(action="retry_partner_bitrix_sync", target_id=str(partner.id), target_type="partner")
    return await get_partner(session, partner_id)


async def bind_partner_bitrix_collab(
    session: AsyncSession,
    partner_id: str,
    data: PartnerBitrixCollabBinding,
) -> PartnerRead:
    partner = await session.get(Partner, partner_id)
    if not partner or partner.deleted_at is not None:
        raise NotFound("Partner not found")
    if data.collab_id is not None:
        partner.bitrix_collab_id = data.collab_id
    if data.chat_id is not None:
        if data.chat_id != partner.bitrix_chat_id:
            partner.bitrix_chat_bot_joined_at = None
        partner.bitrix_chat_id = data.chat_id
    if data.root_folder_id is not None:
        partner.bitrix_root_folder_id = data.root_folder_id
    partner.bitrix_collab_status = (
        "linked"
        if partner.bitrix_collab_id and partner.bitrix_chat_id and partner.bitrix_root_folder_id
        else "binding_required"
    )
    await session.flush()
    audit_log(action="bind_partner_bitrix_collab", target_id=str(partner.id), target_type="partner")
    return await get_partner(session, partner_id)


async def delete_partner(session: AsyncSession, partner_id: str) -> None:
    from sqlalchemy import delete as sa_delete

    from app.models.chat import ChatMessage, ChatRoom
    from app.models.client_status_log import ClientStatusLog
    from app.models.court_fee import CourtFee
    from app.models.file_upload import FileUpload
    from app.models.task import Task
    from app.models.transaction import Transaction

    partner = await session.get(Partner, partner_id)
    if not partner or partner.deleted_at is not None:
        raise NotFound("Partner not found")

    client_ids_q = select(Client.id).where(Client.partner_id == partner.id)
    client_ids = list((await session.execute(client_ids_q)).scalars().all())

    if client_ids:
        await session.execute(sa_delete(Task).where(Task.client_id.in_(client_ids)))
        await session.execute(sa_delete(FileUpload).where(FileUpload.client_id.in_(client_ids)))
        await session.execute(sa_delete(ClientStatusLog).where(ClientStatusLog.client_id.in_(client_ids)))

    await session.execute(sa_delete(Transaction).where(Transaction.partner_id == partner.id))
    await session.execute(sa_delete(CourtFee).where(CourtFee.partner_id == partner.id))

    if client_ids:
        await session.execute(sa_delete(Client).where(Client.id.in_(client_ids)))

    room_ids_q = select(ChatRoom.id).where(ChatRoom.partner_id == partner.id)
    room_ids = list((await session.execute(room_ids_q)).scalars().all())
    if room_ids:
        await session.execute(sa_delete(ChatMessage).where(ChatMessage.room_id.in_(room_ids)))
        await session.execute(sa_delete(ChatRoom).where(ChatRoom.id.in_(room_ids)))

    user_id = partner.user_id
    await session.delete(partner)

    from app.models.notification import Notification
    from app.models.settings import LoginHistory, NotificationPreference

    await session.execute(sa_delete(Notification).where(Notification.user_id == user_id))
    await session.execute(sa_delete(NotificationPreference).where(NotificationPreference.user_id == user_id))
    await session.execute(sa_delete(LoginHistory).where(LoginHistory.user_id == user_id))

    user = await session.get(User, user_id)
    if user:
        await session.delete(user)

    await session.flush()

    audit_log(action="delete_partner", target_id=partner_id, target_type="partner")
    logger.info("partner_deleted", partner_id=partner_id)


async def get_partners_stats(session: AsyncSession) -> PartnerStats:
    base = (
        select(func.count())
        .select_from(Partner)
        .join(User, Partner.user_id == User.id)
        .where(Partner.deleted_at.is_(None), User.role != "admin")
    )

    total = (await session.execute(base)).scalar() or 0
    active = (await session.execute(base.where(Partner.status == "active"))).scalar() or 0
    pending = (await session.execute(base.where(Partner.status == "pending"))).scalar() or 0
    clients = (await session.execute(select(func.count()).where(Client.deleted_at.is_(None)))).scalar() or 0

    return PartnerStats(
        total_partners=total,
        active_partners=active,
        total_clients=clients,
        pending_partners=pending,
    )
