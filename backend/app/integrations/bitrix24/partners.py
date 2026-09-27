from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.token_storage import decrypt_token
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


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


def _field_key(value: str) -> str:
    """Match original UF names and Bitrix24's camelCase response names."""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _remote_value(item: dict[str, Any], field_name: str) -> Any:
    wanted = _field_key(field_name)
    for key, value in item.items():
        if _field_key(str(key)) == wanted:
            return value
    return None


def _scalar(value: Any) -> Any:
    if isinstance(value, list):
        return _scalar(value[0]) if value else None
    if isinstance(value, dict):
        for key in ("value", "VALUE", "amount", "AMOUNT"):
            if key in value:
                return _scalar(value[key])
        return None
    return value


def _text(value: Any) -> str:
    scalar = _scalar(value)
    if scalar is None or scalar is False:
        return ""
    return " ".join(str(scalar).split())


def _phone(value: Any) -> str:
    digits = re.sub(r"\D", "", _text(value))
    if len(digits) == 11 and digits.startswith("8"):
        return "7" + digits[1:]
    return digits


def _integer(value: Any) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        return int(Decimal(text.replace(",", ".")))
    except (ValueError, ArithmeticError):
        return None


def _money_cents(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("amount") or value.get("AMOUNT") or value.get("value") or value.get("VALUE")
    text = _text(value)
    if not text:
        return None
    amount = next((part for part in text.split("|") if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", part)), None)
    if amount is None:
        return None
    try:
        return int((Decimal(amount.replace(",", ".")) * 100).quantize(Decimal("1")))
    except (ValueError, ArithmeticError):
        return None


async def partner_profile_differences(
    db: AsyncSession,
    partner: Partner,
    remote_item: dict[str, Any],
) -> set[str]:
    """Return only material differences in cabinet-owned partner fields."""
    user = await db.get(User, partner.user_id)
    comparisons = {
        "company_name": (
            _text(partner.company_name),
            _text(_remote_value(remote_item, PARTNER_FIELDS["company_name"])),
        ),
        "director_name": (
            _text(partner.director_name),
            _text(_remote_value(remote_item, PARTNER_FIELDS["director_name"])),
        ),
        "phone": (_phone(partner.phone), _phone(_remote_value(remote_item, PARTNER_FIELDS["phone"]))),
        "email": (
            _text(user.email if user else None).casefold(),
            _text(_remote_value(remote_item, PARTNER_FIELDS["email"])).casefold(),
        ),
        "legal_address": (
            _text(partner.legal_address),
            _text(_remote_value(remote_item, PARTNER_FIELDS["legal_address"])),
        ),
        "partner_type": (
            _text(partner.partner_type).casefold(),
            _text(_remote_value(remote_item, PARTNER_FIELDS["partner_type"])).casefold(),
        ),
        "inn": (
            re.sub(r"\D", "", _text(partner.inn)),
            re.sub(r"\D", "", _text(_remote_value(remote_item, PARTNER_FIELDS["inn"]))),
        ),
        "kpp": (
            re.sub(r"\D", "", _text(partner.kpp)),
            re.sub(r"\D", "", _text(_remote_value(remote_item, PARTNER_FIELDS["kpp"]))),
        ),
        "court_fee": (
            partner.court_fee_per_client,
            _money_cents(_remote_value(remote_item, PARTNER_FIELDS["court_fee"])),
        ),
        "payment_days": (
            partner.payment_term_days,
            _integer(_remote_value(remote_item, PARTNER_FIELDS["payment_days"])),
        ),
    }
    return {name for name, (local, remote) in comparisons.items() if local != remote}


async def _apply_remote_partner_profile(
    db: AsyncSession,
    mapping: BitrixEntityMap,
    partner: Partner,
    remote_item: dict[str, Any],
) -> bool:
    differences = await partner_profile_differences(db, partner, remote_item)
    now = datetime.now(UTC)
    mapping.last_verified_at = now
    if differences:
        partner.bitrix_sync_status = "conflict"
        partner.bitrix_sync_error_code = "REMOTE_PROFILE_CHANGED"
        await db.flush()
        return True

    partner.bitrix_sync_status = "synced"
    partner.bitrix_sync_error_code = None
    partner.bitrix_synced_at = now
    mapping.last_synced_at = now
    await db.flush()
    return False


async def mark_remote_partner_conflict(
    db: AsyncSession,
    *,
    member_id: str,
    event_name: str,
    payload: dict[str, Any],
    remote_item: dict[str, Any] | None = None,
) -> bool:
    """Verify a remote update and flag only material profile differences."""
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
    if remote_item is None:
        installation = await db.get(BitrixInstallation, member_id)
        if installation is None:
            return False
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            result = await remote.call(
                "crm.item.get",
                {
                    "entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
                    "id": str(remote_id),
                    "useOriginalUfNames": "Y",
                },
            )
        remote_item = result.get("item", {}) if isinstance(result, dict) else {}
        if not isinstance(remote_item, dict):
            raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 returned an unexpected partner item")
    return await _apply_remote_partner_profile(db, mapping, partner, remote_item)


async def reconcile_remote_partner_profiles(db: AsyncSession, *, limit: int = 25) -> dict[str, int]:
    """Repair false conflicts and periodically verify mapped partner profiles."""
    installation = await active_installation(db)
    if installation is None:
        return {"claimed": 0, "synced": 0, "conflicts": 0, "failed": 0}

    stale_before = datetime.now(UTC) - timedelta(hours=settings.BITRIX_RECONCILE_AFTER_HOURS)
    mappings = list(
        (
            await db.scalars(
                select(BitrixEntityMap)
                .join(Partner, Partner.id == BitrixEntityMap.local_entity_id)
                .where(
                    BitrixEntityMap.member_id == installation.member_id,
                    BitrixEntityMap.local_entity_type == PARTNER_ENTITY_TYPE,
                    Partner.deleted_at.is_(None),
                    or_(
                        Partner.bitrix_sync_status == "conflict",
                        BitrixEntityMap.last_verified_at.is_(None),
                        BitrixEntityMap.last_verified_at < stale_before,
                    ),
                )
                .order_by(
                    case((Partner.bitrix_sync_status == "conflict", 0), else_=1),
                    BitrixEntityMap.last_verified_at.asc().nullsfirst(),
                    BitrixEntityMap.created_at,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    if not mappings:
        return {"claimed": 0, "synced": 0, "conflicts": 0, "failed": 0}

    synced = 0
    conflicts = 0
    failed = 0
    token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, token) as remote:
        for mapping in mappings:
            partner = await db.get(Partner, mapping.local_entity_id)
            if partner is None:
                failed += 1
                continue
            try:
                result = await remote.call(
                    "crm.item.get",
                    {
                        "entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
                        "id": mapping.bitrix_entity_id,
                        "useOriginalUfNames": "Y",
                    },
                )
            except Bitrix24Error:
                failed += 1
                continue
            remote_item = result.get("item", {}) if isinstance(result, dict) else {}
            if not isinstance(remote_item, dict):
                failed += 1
                continue
            if await _apply_remote_partner_profile(db, mapping, partner, remote_item):
                conflicts += 1
            else:
                synced += 1
    await db.commit()
    return {"claimed": len(mappings), "synced": synced, "conflicts": conflicts, "failed": failed}
