from __future__ import annotations

import uuid
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.partners import PARTNER_ENTITY_TYPE, active_installation
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.enums import ClientStatus, ClientType
from app.models.partner import Partner
from app.services.audit import audit_log

CLIENT_CONTACT_ENTITY_TYPE = "client_contact"
CLIENT_DEAL_ENTITY_TYPE = "client_deal"
CLIENT_CONTACT_CREATE_METHOD = "crm.contact.add"
CLIENT_DEAL_CREATE_METHOD = "crm.deal.add"
CLIENT_DEAL_CATEGORY_ID = 3
CLIENT_DEAL_STAGE_ID = "C3:NEW"
CLIENT_UID_FIELD = "UF_CRM_P24_CUID_ITN"
SELF_ORIGINATOR_ID = "partner_cabinet"
CLIENT_DEAL_ADD_EVENT = "ONCRMDEALADD"
CLIENT_DEAL_UPDATE_EVENT = "ONCRMDEALUPDATE"
CLIENT_DEAL_EVENTS = {CLIENT_DEAL_ADD_EVENT, CLIENT_DEAL_UPDATE_EVENT}
CLIENT_EVENT_HANDLER = "https://finzdorovie.ru/api/v1/integrations/bitrix24/handler"
CLIENT_DEAL_FIELDS = {
    "region": "UF_CRM_DEAL_YRITECH_CLIENT_REGION",
    "arbitrage_court": "UF_CRM_DEAL_YRITECH_ARBITRAGE_COURT",
    "case_number": "UF_CRM_DEAL_YRITECH_CASE_NUMBER",
    "court_date": "UF_CRM_DEAL_YRITECH_COURT_DATE",
    "client_type": "UF_CRM_DEAL_YRITECH_CLIENT_TYPE",
    "client_status": "UF_CRM_DEAL_YRITECH_CLIENT_STATUS",
}


def extract_client_deal_event_reference(event_name: str, payload: dict[str, Any]) -> str | None:
    if event_name.upper() not in CLIENT_DEAL_EVENTS:
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        fields = data.get("FIELDS") or data.get("fields")
        if isinstance(fields, dict) and (fields.get("ID") or fields.get("id")):
            return str(fields.get("ID") or fields.get("id"))
    for key in ("data[FIELDS][ID]", "data[fields][id]"):
        if payload.get(key):
            return str(payload[key])
    return None


def _split_full_name(full_name: str) -> tuple[str, str | None, str | None]:
    parts = full_name.strip().split()
    if not parts:
        return "Клиент", None, None
    last_name = parts[0]
    name = parts[1] if len(parts) > 1 else None
    second_name = " ".join(parts[2:]) if len(parts) > 2 else None
    return last_name, name, second_name


def build_client_contact_payload(client: Client) -> dict[str, Any]:
    last_name, name, second_name = _split_full_name(client.full_name)
    fields: dict[str, Any] = {
        "LAST_NAME": last_name,
        "ORIGINATOR_ID": SELF_ORIGINATOR_ID,
        "ORIGIN_ID": str(client.id),
        CLIENT_UID_FIELD: str(client.id),
    }
    optional: dict[str, Any] = {
        "NAME": name,
        "SECOND_NAME": second_name,
        "BIRTHDATE": client.date_of_birth.isoformat() if client.date_of_birth else None,
        "PHONE": [{"VALUE": client.phone, "VALUE_TYPE": "WORK"}] if client.phone else None,
        "EMAIL": [{"VALUE": client.email, "VALUE_TYPE": "WORK"}] if client.email else None,
    }
    fields.update({key: value for key, value in optional.items() if value})
    return {"fields": fields}


def build_client_deal_payload(client: Client, partner_item_id: str, contact_id: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "TITLE": f"Клиент: {client.full_name}",
        "CATEGORY_ID": CLIENT_DEAL_CATEGORY_ID,
        "STAGE_ID": CLIENT_DEAL_STAGE_ID,
        "CONTACT_ID": contact_id,
        f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}": partner_item_id,
        "ORIGINATOR_ID": SELF_ORIGINATOR_ID,
        "ORIGIN_ID": str(client.id),
        CLIENT_UID_FIELD: str(client.id),
        CLIENT_DEAL_FIELDS["client_type"]: client.type,
        CLIENT_DEAL_FIELDS["client_status"]: client.status,
    }
    optional: dict[str, Any] = {
        CLIENT_DEAL_FIELDS["region"]: client.region,
        CLIENT_DEAL_FIELDS["arbitrage_court"]: client.arbitrage_court,
        CLIENT_DEAL_FIELDS["case_number"]: client.case_number,
        CLIENT_DEAL_FIELDS["court_date"]: client.court_procedure_date.isoformat()
        if client.court_procedure_date
        else None,
    }
    fields.update({key: value for key, value in optional.items() if value})
    return {"fields": fields}


async def _has_mapping(db: AsyncSession, client_id: uuid.UUID, member_id: str, entity_type: str) -> bool:
    return (
        await db.scalar(
            select(BitrixEntityMap.id).where(
                BitrixEntityMap.member_id == member_id,
                BitrixEntityMap.local_entity_type == entity_type,
                BitrixEntityMap.local_entity_id == client_id,
            )
        )
        is not None
    )


async def schedule_client_creation(
    db: AsyncSession,
    client: Client,
    *,
    partner: Partner | None = None,
    retry: bool = False,
) -> bool:
    """Queue the contact projection; its completion queues the dependent deal."""
    installation = await active_installation(db)
    if installation is None:
        client.bitrix_sync_status = "not_scheduled"
        client.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND"
        return False
    if client.bitrix_deal_id or await _has_mapping(db, client.id, installation.member_id, CLIENT_DEAL_ENTITY_TYPE):
        client.bitrix_sync_status = "synced"
        client.bitrix_sync_error_code = None
        return False

    partner = partner or await db.get(Partner, client.partner_id)
    if partner is None or not partner.bitrix_partner_item_id:
        client.bitrix_sync_status = "pending"
        client.bitrix_sync_error_code = "PARTNER_NOT_SYNCED"
        client.bitrix_sync_requested_at = datetime.now(UTC)
        await db.flush()
        return False

    if client.bitrix_contact_id:
        await enqueue_client_deal(
            db,
            client=client,
            partner=partner,
            member_id=installation.member_id,
            contact_id=client.bitrix_contact_id,
            retry=retry,
        )
        client.bitrix_sync_status = "pending"
        client.bitrix_sync_error_code = None
        client.bitrix_sync_requested_at = datetime.now(UTC)
        await db.flush()
        return True

    operation_key = f"client:contact:{client.id}:v1"
    operation = await db.scalar(
        select(BitrixOutboxOperation).where(
            BitrixOutboxOperation.member_id == installation.member_id,
            BitrixOutboxOperation.operation_key == operation_key,
        )
    )
    if operation is not None:
        if retry and operation.status == "failed":
            operation.status = "pending"
            operation.attempts = 0
            operation.error_code = None
            operation.next_attempt_at = None
            operation.locked_at = None
            operation.completed_at = None
            operation.result_reference = None
        elif operation.status in {"pending", "processing", "retry", "completed"}:
            return False
    else:
        await db.execute(
            insert(BitrixOutboxOperation)
            .values(
                id=uuid.uuid4(),
                member_id=installation.member_id,
                operation_key=operation_key,
                local_entity_type=CLIENT_CONTACT_ENTITY_TYPE,
                local_entity_id=client.id,
                bitrix_method=CLIENT_CONTACT_CREATE_METHOD,
                payload=build_client_contact_payload(client),
                correlation_id=uuid.uuid4(),
                max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        )

    client.bitrix_sync_status = "pending"
    client.bitrix_sync_error_code = None
    client.bitrix_sync_requested_at = datetime.now(UTC)
    await db.flush()
    return True


async def enqueue_client_deal(
    db: AsyncSession,
    *,
    client: Client,
    partner: Partner,
    member_id: str,
    contact_id: str,
    retry: bool = False,
) -> None:
    operation_key = f"client:deal:{client.id}:v1"
    operation = await db.scalar(
        select(BitrixOutboxOperation).where(
            BitrixOutboxOperation.member_id == member_id,
            BitrixOutboxOperation.operation_key == operation_key,
        )
    )
    if operation is not None:
        if retry and operation.status == "failed":
            operation.status = "pending"
            operation.attempts = 0
            operation.error_code = None
            operation.next_attempt_at = None
            operation.locked_at = None
            operation.completed_at = None
            operation.result_reference = None
        return
    await db.execute(
        insert(BitrixOutboxOperation)
        .values(
            id=uuid.uuid4(),
            member_id=member_id,
            operation_key=operation_key,
            local_entity_type=CLIENT_DEAL_ENTITY_TYPE,
            local_entity_id=client.id,
            bitrix_method=CLIENT_DEAL_CREATE_METHOD,
            payload=build_client_deal_payload(client, partner.bitrix_partner_item_id or "", contact_id),
            correlation_id=uuid.uuid4(),
            max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
        )
        .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
    )


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    with suppress(ValueError):
        return date.fromisoformat(str(value)[:10])
    return None


def _first_communication(value: Any, *, max_length: int) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if isinstance(item, dict) and item.get("VALUE"):
            return str(item["VALUE"]).strip()[:max_length] or None
    return None


def _remote_full_name(contact: dict[str, Any]) -> str:
    return " ".join(
        str(contact.get(field) or "").strip()
        for field in ("LAST_NAME", "NAME", "SECOND_NAME")
        if str(contact.get(field) or "").strip()
    )


def _valid_enum_value(value: Any, enum_type: type[ClientType] | type[ClientStatus]) -> str | None:
    candidate = str(value or "").strip()
    return candidate if candidate in {item.value for item in enum_type} else None


def _mark_inbound_failure(receipt: BitrixInboundEvent, code: str) -> bool:
    receipt.status = "failed"
    receipt.error_code = code[:100]
    receipt.attempts += 1
    return False


async def _supersede_failed_receipts(
    db: AsyncSession,
    receipt: BitrixInboundEvent,
    *,
    processed_at: datetime,
) -> None:
    """Keep one current attention item per remote deal."""
    await db.execute(
        update(BitrixInboundEvent)
        .where(
            BitrixInboundEvent.id != receipt.id,
            BitrixInboundEvent.member_id == receipt.member_id,
            BitrixInboundEvent.remote_entity_type == CLIENT_DEAL_ENTITY_TYPE,
            BitrixInboundEvent.remote_entity_id == receipt.remote_entity_id,
            BitrixInboundEvent.status == "failed",
        )
        .values(status="ignored", error_code=None, processed_at=processed_at)
    )


async def _ignore_current_state(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    """Close this receipt and any obsolete warnings for the same remote deal."""
    now = datetime.now(UTC)
    await _supersede_failed_receipts(db, receipt, processed_at=now)
    receipt.status = "ignored"
    receipt.error_code = None
    receipt.processed_at = now
    receipt.attempts += 1
    return True


async def _mark_current_state_failure(
    db: AsyncSession,
    receipt: BitrixInboundEvent,
    code: str,
) -> bool:
    now = datetime.now(UTC)
    await _supersede_failed_receipts(db, receipt, processed_at=now)
    return _mark_inbound_failure(receipt, code)


async def _complete_existing_client_update(
    db: AsyncSession,
    *,
    receipt: BitrixInboundEvent,
    client: Client,
    partner: Partner,
) -> bool:
    """Apply a Bitrix deal partner change to an already imported client."""
    now = datetime.now(UTC)
    previous_partner_id = client.partner_id
    client.partner_id = partner.id
    client.bitrix_sync_status = "synced"
    client.bitrix_sync_error_code = None
    client.bitrix_synced_at = now

    if previous_partner_id != partner.id:
        from app.models.court_fee import CourtFee

        await db.execute(
            update(CourtFee)
            .where(CourtFee.client_id == client.id, CourtFee.deleted_at.is_(None))
            .values(partner_id=partner.id)
        )

    await _supersede_failed_receipts(db, receipt, processed_at=now)
    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = now
    receipt.attempts += 1
    audit_log(
        action="update_client_partner_from_bitrix",
        target_id=str(client.id),
        target_type="client",
        details={
            "previous_partner_id": str(previous_partner_id),
            "partner_id": str(partner.id),
            "bitrix_deal_id": receipt.remote_entity_id,
        },
    )
    return True


async def process_client_deal_add_event(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    """Create or relink a cabinet client from an Arbitration deal event."""
    receipt.status = "processing"
    receipt.error_code = None
    await db.flush()
    if receipt.remote_entity_type != CLIENT_DEAL_ENTITY_TYPE or not receipt.remote_entity_id:
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        return True

    existing_mapping = await db.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == receipt.member_id,
            BitrixEntityMap.local_entity_type == CLIENT_DEAL_ENTITY_TYPE,
            BitrixEntityMap.bitrix_entity_type == "crm_deal",
            BitrixEntityMap.bitrix_entity_id == receipt.remote_entity_id,
        )
    )
    existing_client = await db.get(Client, existing_mapping.local_entity_id) if existing_mapping is not None else None

    installation = await db.get(BitrixInstallation, receipt.member_id)
    if installation is None:
        return _mark_inbound_failure(receipt, "INSTALLATION_NOT_FOUND")
    deal_loaded = False
    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            deal = await remote.call("crm.deal.get", {"ID": receipt.remote_entity_id})
            if not isinstance(deal, dict):
                return _mark_inbound_failure(receipt, "INVALID_DEAL_RESPONSE")
            deal_loaded = True
            if str(deal.get("CATEGORY_ID") or "") != str(CLIENT_DEAL_CATEGORY_ID):
                return await _ignore_current_state(db, receipt)
            if existing_client is None and str(deal.get("ORIGINATOR_ID") or "").lower() == SELF_ORIGINATOR_ID:
                return await _ignore_current_state(db, receipt)

            partner_remote_id = deal.get(f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}")
            if not partner_remote_id:
                # An unlinked Bitrix deal is not a cabinet client yet.  Whether it was
                # created directly in this funnel or moved here, wait silently until a
                # partner is selected; that update will trigger the import.  Removing
                # the link from an already imported client remains actionable.
                if existing_client is None:
                    return await _ignore_current_state(db, receipt)
                return await _mark_current_state_failure(db, receipt, "PARTNER_NOT_LINKED")
            partner_mapping = await db.scalar(
                select(BitrixEntityMap).where(
                    BitrixEntityMap.member_id == receipt.member_id,
                    BitrixEntityMap.local_entity_type == PARTNER_ENTITY_TYPE,
                    BitrixEntityMap.bitrix_entity_id == str(partner_remote_id),
                )
            )
            if partner_mapping is None:
                return await _mark_current_state_failure(db, receipt, "PARTNER_NOT_FOUND")
            partner = await db.get(Partner, partner_mapping.local_entity_id)
            if partner is None:
                return await _mark_current_state_failure(db, receipt, "PARTNER_NOT_FOUND")

            if existing_client is not None:
                return await _complete_existing_client_update(
                    db,
                    receipt=receipt,
                    client=existing_client,
                    partner=partner,
                )

            contact_id = str(deal.get("CONTACT_ID") or "").strip()
            if not contact_id or contact_id == "0":
                return _mark_inbound_failure(receipt, "CONTACT_NOT_LINKED")
            existing_contact = await db.scalar(
                select(BitrixEntityMap.id).where(
                    BitrixEntityMap.member_id == receipt.member_id,
                    BitrixEntityMap.bitrix_entity_type == "crm_contact",
                    BitrixEntityMap.bitrix_entity_id == contact_id,
                )
            )
            if existing_contact is not None:
                return _mark_inbound_failure(receipt, "CONTACT_ALREADY_LINKED")
            contact = await remote.call("crm.contact.get", {"ID": contact_id})
            if not isinstance(contact, dict):
                return _mark_inbound_failure(receipt, "INVALID_CONTACT_RESPONSE")
    except Bitrix24Error as exc:
        if (
            not deal_loaded
            and exc.status_code in {400, 404}
            and not exc.code.strip()
            and exc.description.strip().casefold() == "not found"
        ):
            return await _ignore_current_state(db, receipt)
        return _mark_inbound_failure(receipt, exc.code)

    full_name = _remote_full_name(contact)
    client_type = _valid_enum_value(deal.get(CLIENT_DEAL_FIELDS["client_type"]), ClientType)
    client_status = _valid_enum_value(deal.get(CLIENT_DEAL_FIELDS["client_status"]), ClientStatus)
    if not full_name:
        return _mark_inbound_failure(receipt, "CLIENT_NAME_REQUIRED")
    if client_type is None:
        return _mark_inbound_failure(receipt, "CLIENT_TYPE_REQUIRED")
    if client_status is None:
        return _mark_inbound_failure(receipt, "CLIENT_STATUS_REQUIRED")

    now = datetime.now(UTC)
    client = Client(
        partner_id=partner.id,
        type=client_type,
        status=client_status,
        full_name=full_name[:255],
        date_of_birth=_parse_date(contact.get("BIRTHDATE")),
        phone=_first_communication(contact.get("PHONE"), max_length=20),
        email=_first_communication(contact.get("EMAIL"), max_length=255),
        region=str(deal.get(CLIENT_DEAL_FIELDS["region"]) or "").strip()[:100] or None,
        arbitrage_court=str(deal.get(CLIENT_DEAL_FIELDS["arbitrage_court"]) or "").strip()[:255] or None,
        case_number=str(deal.get(CLIENT_DEAL_FIELDS["case_number"]) or "").strip()[:50] or None,
        court_procedure_date=_parse_date(deal.get(CLIENT_DEAL_FIELDS["court_date"])),
        bitrix_sync_status="synced",
        bitrix_contact_id=contact_id,
        bitrix_deal_id=receipt.remote_entity_id,
        bitrix_synced_at=now,
    )
    db.add(client)
    await db.flush()
    for local_type, remote_type, remote_id in (
        (CLIENT_CONTACT_ENTITY_TYPE, "crm_contact", contact_id),
        (CLIENT_DEAL_ENTITY_TYPE, "crm_deal", receipt.remote_entity_id),
    ):
        await db.execute(
            insert(BitrixEntityMap)
            .values(
                id=uuid.uuid4(),
                member_id=receipt.member_id,
                local_entity_type=local_type,
                local_entity_id=client.id,
                bitrix_entity_type=remote_type,
                bitrix_entity_id=remote_id,
                sync_version=1,
                last_synced_at=now,
                last_verified_at=now,
            )
            .on_conflict_do_nothing()
        )

    from app.services.finance_service import create_court_fee_for_client

    await create_court_fee_for_client(db, client, partner)
    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = now
    receipt.attempts += 1
    await _supersede_failed_receipts(db, receipt, processed_at=now)
    audit_log(action="import_client_from_bitrix", target_id=str(client.id), target_type="client")
    return True


async def retry_client_deal_events(db: AsyncSession, *, limit: int = 25) -> tuple[int, int]:
    retryable_errors = {
        "TIMEOUT",
        "TRANSPORT_ERROR",
        "QUERY_LIMIT_EXCEEDED",
        "OPERATION_TIME_LIMIT",
        "INTERNAL_SERVER_ERROR",
    }
    receipts = list(
        (
            await db.scalars(
                select(BitrixInboundEvent)
                .where(
                    BitrixInboundEvent.remote_entity_type == CLIENT_DEAL_ENTITY_TYPE,
                    or_(
                        BitrixInboundEvent.status == "received",
                        and_(
                            BitrixInboundEvent.status == "failed",
                            BitrixInboundEvent.error_code.in_(retryable_errors),
                            BitrixInboundEvent.attempts < settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
                        ),
                    ),
                )
                .order_by(BitrixInboundEvent.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    completed = 0
    for receipt in receipts:
        if await process_client_deal_add_event(db, receipt):
            completed += 1
    await db.commit()
    return len(receipts), completed
