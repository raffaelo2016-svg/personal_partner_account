from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixOutboxOperation
from app.models.partner import Partner
from app.models.user import User

PARTNER_ENTITY_TYPE = "partner_smart_process"
PARTNER_CREATE_METHOD = "crm.item.add"
PARTNER_CATEGORY_ID = 19
PARTNER_STAGE_ID = "DT1070_19:NEW"

# Existing fields were confirmed by the stage-1 survey. The named fields below
# are provisioned once in the same smart process and then stay stable.
PARTNER_FIELDS = {
    "company_name": "UF_CRM_31_1733299628342",
    "director_name": "UF_CRM_31_1733299716310",
    "phone": "UF_CRM_31_1733299746918",
    "email": "UF_CRM_31_1733299758806",
    "legal_address": "UF_CRM_31_1743589990820",
    "partner_type": "UF_CRM_16_YRITECH_PARTNER_TYPE",
    "inn": "UF_CRM_16_YRITECH_PARTNER_INN",
    "kpp": "UF_CRM_16_YRITECH_PARTNER_KPP",
    "court_fee": "UF_CRM_16_YRITECH_COURT_FEE",
    "payment_days": "UF_CRM_16_YRITECH_PAYMENT_DAYS",
}


def _money_rubles(cents: int) -> str:
    rubles = Decimal(cents) / Decimal(100)
    return f"{rubles:.2f}|RUB"


def build_partner_create_payload(partner: Partner, email: str | None) -> dict[str, Any]:
    """Build the minimum Bitrix24 projection; cabinet data stays authoritative."""
    fields: dict[str, Any] = {
        "title": partner.company_name,
        "xmlId": str(partner.id),
        "categoryId": PARTNER_CATEGORY_ID,
        "stageId": PARTNER_STAGE_ID,
        PARTNER_FIELDS["company_name"]: partner.company_name,
        PARTNER_FIELDS["director_name"]: partner.director_name,
        PARTNER_FIELDS["phone"]: partner.phone,
        PARTNER_FIELDS["partner_type"]: partner.partner_type,
        PARTNER_FIELDS["inn"]: partner.inn,
        PARTNER_FIELDS["court_fee"]: _money_rubles(partner.court_fee_per_client),
        PARTNER_FIELDS["payment_days"]: partner.payment_term_days,
    }
    optional = {
        PARTNER_FIELDS["email"]: email,
        PARTNER_FIELDS["legal_address"]: partner.legal_address,
        PARTNER_FIELDS["kpp"]: partner.kpp,
    }
    fields.update({key: value for key, value in optional.items() if value})
    return {
        "entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
        "useOriginalUfNames": "Y",
        "fields": fields,
    }


async def active_installation(db: AsyncSession) -> BitrixInstallation | None:
    return await db.scalar(
        select(BitrixInstallation)
        .where(
            BitrixInstallation.portal_domain == settings.BITRIX_ALLOWED_DOMAIN,
            BitrixInstallation.status == "L",
        )
        .limit(1)
    )


async def _has_partner_mapping(db: AsyncSession, partner_id: uuid.UUID, member_id: str) -> bool:
    mapping_id = await db.scalar(
        select(BitrixEntityMap.id).where(
            BitrixEntityMap.member_id == member_id,
            BitrixEntityMap.local_entity_type == PARTNER_ENTITY_TYPE,
            BitrixEntityMap.local_entity_id == partner_id,
        )
    )
    return mapping_id is not None


async def schedule_partner_creation(db: AsyncSession, partner: Partner, *, retry: bool = False) -> bool:
    """Queue a partner once without committing the caller's transaction."""
    if partner.status != "active":
        return False
    installation = await active_installation(db)
    if installation is None:
        partner.bitrix_sync_status = "not_scheduled"
        partner.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND"
        return False
    if partner.bitrix_partner_item_id or await _has_partner_mapping(db, partner.id, installation.member_id):
        partner.bitrix_sync_status = "synced"
        partner.bitrix_sync_error_code = None
        return False

    user = await db.get(User, partner.user_id)
    operation_key = f"partner:create:{partner.id}:v1"
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
        statement = (
            insert(BitrixOutboxOperation)
            .values(
                id=uuid.uuid4(),
                member_id=installation.member_id,
                operation_key=operation_key,
                local_entity_type=PARTNER_ENTITY_TYPE,
                local_entity_id=partner.id,
                bitrix_method=PARTNER_CREATE_METHOD,
                payload=build_partner_create_payload(partner, user.email if user else None),
                correlation_id=uuid.uuid4(),
                max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        )
        await db.execute(statement)

    partner.bitrix_sync_status = "pending"
    partner.bitrix_sync_error_code = None
    partner.bitrix_sync_requested_at = datetime.now(UTC)
    if partner.bitrix_collab_status == "not_linked":
        partner.bitrix_collab_status = "binding_required"
    await db.flush()
    return True


def _event_field(payload: dict[str, Any], name: str) -> Any:
    data = payload.get("data")
    if isinstance(data, dict):
        fields = data.get("FIELDS") or data.get("fields")
        if isinstance(fields, dict):
            value = fields.get(name) or fields.get(name.lower())
            if value is not None:
                return value
    for key in (
        f"data[FIELDS][{name}]",
        f"data[fields][{name.lower()}]",
        f"FIELDS[{name}]",
    ):
        if key in payload:
            return payload[key]
    return None


async def mark_remote_partner_conflict(
    db: AsyncSession,
    *,
    member_id: str,
    event_name: str,
    payload: dict[str, Any],
) -> bool:
    """Flag a remote profile edit; never copy it over cabinet requisites."""
    if event_name.upper() != "ONCRMDYNAMICITEMUPDATE":
        return False
    entity_type_id = _event_field(payload, "ENTITY_TYPE_ID")
    remote_id = _event_field(payload, "ID")
    if str(entity_type_id or "") != str(settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID) or not remote_id:
        return False
    mapping = await db.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == member_id,
            BitrixEntityMap.local_entity_type == PARTNER_ENTITY_TYPE,
            BitrixEntityMap.bitrix_entity_id == str(remote_id),
        )
    )
    if mapping is None:
        return False
    partner = await db.get(Partner, mapping.local_entity_id)
    if partner is None:
        return False
    partner.bitrix_sync_status = "conflict"
    partner.bitrix_sync_error_code = "REMOTE_PROFILE_CHANGED"
    await db.flush()
    return True
