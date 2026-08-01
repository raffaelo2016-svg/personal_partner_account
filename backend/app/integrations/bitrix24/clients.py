from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.partners import active_installation
from app.models.bitrix_sync import BitrixEntityMap, BitrixOutboxOperation
from app.models.client import Client
from app.models.partner import Partner

CLIENT_CONTACT_ENTITY_TYPE = "client_contact"
CLIENT_DEAL_ENTITY_TYPE = "client_deal"
CLIENT_CONTACT_CREATE_METHOD = "crm.contact.add"
CLIENT_DEAL_CREATE_METHOD = "crm.deal.add"
CLIENT_DEAL_CATEGORY_ID = 3
CLIENT_DEAL_STAGE_ID = "C3:NEW"
CLIENT_UID_FIELD = "UF_CRM_P24_CUID_ITN"
SELF_ORIGINATOR_ID = "partner_cabinet"
CLIENT_DEAL_FIELDS = {
    "region": "UF_CRM_DEAL_YRITECH_CLIENT_REGION",
    "arbitrage_court": "UF_CRM_DEAL_YRITECH_ARBITRAGE_COURT",
    "case_number": "UF_CRM_DEAL_YRITECH_CASE_NUMBER",
    "court_date": "UF_CRM_DEAL_YRITECH_COURT_DATE",
    "client_type": "UF_CRM_DEAL_YRITECH_CLIENT_TYPE",
    "client_status": "UF_CRM_DEAL_YRITECH_CLIENT_STATUS",
}


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
