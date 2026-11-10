import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequest, NotFound
from app.models.client import Client
from app.models.client_status_log import ClientStatusLog
from app.models.enums import ClientStatus
from app.services.audit import audit_log

logger = structlog.get_logger()

STATUS_TRANSITIONS: dict[ClientStatus, list[ClientStatus]] = {
    ClientStatus.DOCUMENTS_COLLECTION: [ClientStatus.DOCUMENTS_FORMATION],
    ClientStatus.DOCUMENTS_FORMATION: [ClientStatus.SENT_TO_COURT, ClientStatus.DOCUMENTS_COLLECTION],
    ClientStatus.SENT_TO_COURT: [ClientStatus.DOCUMENTS_DECISION, ClientStatus.DOCUMENTS_FORMATION],
    ClientStatus.DOCUMENTS_DECISION: [ClientStatus.WAITING_HEARING, ClientStatus.SENT_TO_COURT],
    ClientStatus.WAITING_HEARING: [ClientStatus.RESTRUCTURING, ClientStatus.DOCUMENTS_DECISION],
    ClientStatus.RESTRUCTURING: [ClientStatus.AUCTION, ClientStatus.WAITING_HEARING],
    ClientStatus.AUCTION: [ClientStatus.REALIZATION, ClientStatus.RESTRUCTURING],
    ClientStatus.REALIZATION: [ClientStatus.AUCTION, ClientStatus.COMPLETED],
    ClientStatus.COMPLETED: [ClientStatus.REALIZATION],
}

STAGE_ORDER: list[ClientStatus] = [
    ClientStatus.DOCUMENTS_COLLECTION,
    ClientStatus.DOCUMENTS_FORMATION,
    ClientStatus.SENT_TO_COURT,
    ClientStatus.DOCUMENTS_DECISION,
    ClientStatus.WAITING_HEARING,
    ClientStatus.RESTRUCTURING,
    ClientStatus.AUCTION,
    ClientStatus.REALIZATION,
    ClientStatus.COMPLETED,
]


async def change_status(
    session: AsyncSession,
    client_id: str,
    new_status_str: str,
    user_id: str,
    *,
    comment: str | None = None,
    partner_id: str | None = None,
) -> Client:
    client = await session.get(Client, client_id)
    if not client or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise NotFound("Client not found")

    try:
        current = ClientStatus(client.status)
        target = ClientStatus(new_status_str)
    except ValueError as exc:
        logger.warning(
            "status_change_rejected",
            client_id=str(client.id),
            reason="invalid_status",
            requested=new_status_str,
        )
        raise BadRequest(f"Invalid status: {new_status_str}") from exc

    allowed = STATUS_TRANSITIONS.get(current, [])
    if target not in allowed:
        logger.warning(
            "status_change_rejected",
            client_id=str(client.id),
            reason="transition_not_allowed",
            from_status=current.value,
            to_status=target.value,
        )
        raise BadRequest(
            f"Transition from '{current.value}' to '{target.value}' is not allowed. "
            f"Allowed: {[s.value for s in allowed]}"
        )

    old_status = client.status
    client.status = target.value
    await session.flush()

    log_entry = ClientStatusLog(
        client_id=client.id,
        from_status=old_status,
        to_status=target.value,
        changed_by=user_id,
        comment=comment,
    )
    session.add(log_entry)
    await session.flush()

    # Введение клиента в процедуру даёт агенту начисление (одно дело — одно начисление).
    if target.value == settings.AGENT_ACCRUAL_STATUS:
        from app.services.agent_service import accrue_for_client

        await accrue_for_client(session, client)

    audit_log(
        action="change_client_status",
        user_id=user_id,
        target_id=str(client.id),
        target_type="client",
        details={"from": old_status, "to": target.value},
    )
    logger.info("client_status_changed", client_id=str(client.id), from_status=old_status, to_status=target.value)
    return client


async def get_status_history(
    session: AsyncSession,
    client_id: str,
    *,
    partner_id: str | None = None,
) -> list[ClientStatusLog]:
    client = await session.get(Client, client_id)
    if not client or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise NotFound("Client not found")

    result = await session.execute(
        select(ClientStatusLog)
        .where(ClientStatusLog.client_id == client_id)
        .order_by(ClientStatusLog.changed_at.desc())
    )
    return list(result.scalars().all())
