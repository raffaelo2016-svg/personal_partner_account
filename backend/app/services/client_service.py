import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.client import Client
from app.models.notification import Notification
from app.models.partner import Partner
from app.models.user import User
from app.schemas.client import ClientCreate, ClientRead, ClientStats, ClientUpdate
from app.services.audit import audit_log

logger = structlog.get_logger()


def _client_to_read(
    c: Client,
    *,
    partner_name: str | None = None,
    court_fee_per_client: int | None = None,
) -> ClientRead:
    return ClientRead(
        id=str(c.id),
        partner_id=str(c.partner_id),
        partner_name=partner_name,
        type=c.type,
        status=c.status,
        full_name=c.full_name,
        date_of_birth=c.date_of_birth,
        passport_series=c.passport_series,
        passport_number=c.passport_number,
        passport_issue_date=c.passport_issue_date,
        passport_issued_by=c.passport_issued_by,
        registration_address=c.registration_address,
        inn=c.inn,
        snils=c.snils,
        phone=c.phone,
        email=c.email,
        region=c.region,
        arbitrage_court=c.arbitrage_court,
        case_number=c.case_number,
        court_procedure_date=c.court_procedure_date,
        court_fee_per_client=court_fee_per_client,
        bitrix_sync_status=c.bitrix_sync_status,
        bitrix_sync_error_code=c.bitrix_sync_error_code,
        bitrix_contact_id=c.bitrix_contact_id,
        bitrix_deal_id=c.bitrix_deal_id,
        bitrix_sync_requested_at=c.bitrix_sync_requested_at,
        bitrix_synced_at=c.bitrix_synced_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def _get_partner_id_for_user(session: AsyncSession, user_id: str) -> str:
    result = await session.execute(select(Partner).where(Partner.user_id == user_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise NotFound("Partner profile not found")
    return str(partner.id)


BEFORE_COURT_STATUSES = ["documents_collection", "documents_formation", "sent_to_court", "documents_decision"]
IN_COURT_STATUSES = ["waiting_hearing", "restructuring", "auction"]


async def list_clients(
    session: AsyncSession,
    *,
    partner_id: str | None = None,
    search: str | None = None,
    client_type: str | None = None,
    status: str | None = None,
    category: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[ClientRead], int]:
    base_q = select(Client).where(Client.deleted_at.is_(None))
    if partner_id:
        base_q = base_q.where(Client.partner_id == partner_id)
    if search:
        pattern = f"%{search}%"
        base_q = base_q.outerjoin(Partner, Client.partner_id == Partner.id).where(
            Client.full_name.ilike(pattern)
            | Client.phone.ilike(pattern)
            | Client.email.ilike(pattern)
            | Client.case_number.ilike(pattern)
            | Partner.company_name.ilike(pattern)
            | Partner.director_name.ilike(pattern)
        )
    if client_type:
        base_q = base_q.where(Client.type == client_type)
    if status:
        base_q = base_q.where(Client.status == status)
    if category == "before_court":
        base_q = base_q.where(Client.status.in_(BEFORE_COURT_STATUSES))
    elif category == "in_court":
        base_q = base_q.where(Client.status.in_(IN_COURT_STATUSES))
    elif category == "completed":
        base_q = base_q.where(Client.status == "realization")

    total = (await session.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    rows = (
        (await session.execute(base_q.order_by(Client.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    )

    partner_ids = {c.partner_id for c in rows}
    partner_map: dict[str, Partner] = {}
    if partner_ids:
        p_rows = (await session.execute(select(Partner).where(Partner.id.in_(partner_ids)))).scalars().all()
        partner_map = {str(p.id): p for p in p_rows}

    return [
        _client_to_read(
            c,
            partner_name=partner_map[str(c.partner_id)].company_name if str(c.partner_id) in partner_map else None,
            court_fee_per_client=partner_map[str(c.partner_id)].court_fee_per_client
            if str(c.partner_id) in partner_map
            else None,
        )
        for c in rows
    ], total


async def get_client(session: AsyncSession, client_id: str, *, partner_id: str | None = None) -> ClientRead:
    client = await session.get(Client, client_id)
    if not client or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise NotFound("Client not found")

    partner = await session.get(Partner, client.partner_id)
    p_name = partner.company_name if partner else None
    return _client_to_read(client, partner_name=p_name)


async def create_client(session: AsyncSession, partner_id: str, data: ClientCreate) -> ClientRead:
    client = Client(
        partner_id=partner_id,
        type=data.type.value,
        status="documents_collection",
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        passport_series=data.passport_series,
        passport_number=data.passport_number,
        passport_issue_date=data.passport_issue_date,
        passport_issued_by=data.passport_issued_by,
        registration_address=data.registration_address,
        inn=data.inn,
        snils=data.snils,
        phone=data.phone,
        email=data.email,
        region=data.region,
        arbitrage_court=data.arbitrage_court,
        case_number=data.case_number,
    )
    session.add(client)
    await session.flush()

    partner = await session.get(Partner, client.partner_id)

    from app.services.finance_service import create_court_fee_for_client

    await create_court_fee_for_client(session, client, partner)

    from app.integrations.bitrix24.clients import schedule_client_creation

    await schedule_client_creation(session, client, partner=partner)
    # Scheduling the Bitrix projection updates the client and makes the
    # SQL-expression-backed ``updated_at`` value expire after the flush. Load
    # it explicitly inside the async session so response serialisation does
    # not attempt implicit IO and raise MissingGreenlet.
    await session.refresh(client, ["updated_at"])

    admin_ids = (
        await session.scalars(select(User.id).where(User.role == "admin", User.is_active.is_(True)))
    ).all()
    session.add_all(
        Notification(
            user_id=admin_id,
            type="new_client",
            title="Новый клиент от партнёра",
            message=f"Партнёр «{partner.company_name}» передал клиента «{client.full_name}».",
            link=f"/admin/clients/{client.id}",
        )
        for admin_id in admin_ids
    )

    audit_log(action="create_client", target_id=str(client.id), target_type="client")
    logger.info("client_created", client_id=str(client.id), partner_id=partner_id)
    p_name = partner.company_name if partner else None
    return _client_to_read(client, partner_name=p_name)


async def retry_client_bitrix_sync(session: AsyncSession, client_id: str) -> ClientRead:
    client = await session.get(Client, client_id)
    if not client or client.deleted_at is not None:
        raise NotFound("Client not found")
    partner = await session.get(Partner, client.partner_id)
    if partner is None:
        raise NotFound("Partner profile not found")

    from app.integrations.bitrix24.clients import schedule_client_creation

    await schedule_client_creation(session, client, partner=partner, retry=True)
    await session.flush()
    return _client_to_read(client, partner_name=partner.company_name)


async def update_client(
    session: AsyncSession,
    client_id: str,
    data: ClientUpdate,
    *,
    partner_id: str | None = None,
) -> ClientRead:
    client = await session.get(Client, client_id)
    if not client or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise NotFound("Client not found")

    update_data = data.model_dump(exclude_unset=True)
    court_date_changed = "court_procedure_date" in update_data
    for key, value in update_data.items():
        if hasattr(client, key):
            setattr(client, key, value)

    await session.flush()
    # updated_at обновляется server-side (onupdate=func.now()) — обновим только его.
    await session.refresh(client, ["updated_at"])

    partner = await session.get(Partner, client.partner_id)

    if court_date_changed and client.court_procedure_date:
        from app.services.finance_service import recalculate_due_date

        await recalculate_due_date(session, client, partner)

    audit_log(action="update_client", target_id=str(client.id), target_type="client", details=update_data)
    logger.info(
        "client_updated",
        client_id=str(client.id),
        fields=list(update_data.keys()),
        court_date_changed=court_date_changed,
    )
    p_name = partner.company_name if partner else None
    return _client_to_read(client, partner_name=p_name)


async def delete_client(
    session: AsyncSession,
    client_id: str,
    *,
    partner_id: str | None = None,
) -> None:
    client = await session.get(Client, client_id)
    if not client:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise NotFound("Client not found")

    from sqlalchemy import delete as sa_delete

    from app.models.client_status_log import ClientStatusLog
    from app.models.court_fee import CourtFee
    from app.models.file_upload import FileUpload
    from app.models.task import Task

    await session.execute(sa_delete(Task).where(Task.client_id == client.id))
    await session.execute(sa_delete(CourtFee).where(CourtFee.client_id == client.id))
    await session.execute(sa_delete(FileUpload).where(FileUpload.client_id == client.id))
    await session.execute(sa_delete(ClientStatusLog).where(ClientStatusLog.client_id == client.id))

    audit_log(action="delete_client", target_id=str(client.id), target_type="client")
    logger.info("client_deleted", client_id=str(client.id))
    await session.delete(client)
    await session.flush()


async def get_client_stats(session: AsyncSession, partner_id: str) -> ClientStats:
    base = select(func.count()).where(Client.deleted_at.is_(None), Client.partner_id == partner_id)

    total = (await session.execute(base)).scalar() or 0
    before_court = (await session.execute(base.where(Client.type == "before_court"))).scalar() or 0
    in_court = (await session.execute(base.where(Client.type == "in_court"))).scalar() or 0
    completed = (await session.execute(base.where(Client.status == "realization"))).scalar() or 0

    new_this_week = (
        await session.execute(base.where(Client.created_at >= func.now() - text("interval '7 days'")))
    ).scalar() or 0

    return ClientStats(
        total=total,
        before_court=before_court,
        in_court=in_court,
        completed=completed,
        new_this_week=new_this_week,
    )
