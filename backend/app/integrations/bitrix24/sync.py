from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.partners import PARTNER_ENTITY_TYPE
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.partner import Partner

logger = structlog.get_logger()

SELF_ORIGINATOR_ID = "partner_cabinet"
_TRANSIENT_ERROR_CODES = {
    "TIMEOUT",
    "TRANSPORT_ERROR",
    "QUERY_LIMIT_EXCEEDED",
    "OPERATION_TIME_LIMIT",
    "INTERNAL_SERVER_ERROR",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def event_fingerprint(payload: dict[str, Any]) -> tuple[str, str]:
    """Return stable event key/hash without retaining credentials or personal data."""
    safe_shape = {
        "event": str(payload.get("event", "UNKNOWN")).upper(),
        "event_id": payload.get("event_id"),
        "event_ts": payload.get("event_ts") or payload.get("ts"),
        "data": payload.get("data"),
    }
    payload_hash = hashlib.sha256(_canonical_json(safe_shape).encode()).hexdigest()
    supplied_key = str(payload.get("event_id") or "").strip()
    event_key = hashlib.sha256(supplied_key.encode()).hexdigest() if supplied_key else payload_hash
    return event_key, payload_hash


def is_self_originated_event(payload: dict[str, Any]) -> bool:
    """Recognize events produced by this integration to prevent sync loops."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return False
    fields = data.get("FIELDS") or data.get("fields") or data
    if not isinstance(fields, dict):
        return False
    originator = fields.get("ORIGINATOR_ID") or fields.get("originatorId")
    return str(originator or "").lower() == SELF_ORIGINATOR_ID


async def register_inbound_event(
    db: AsyncSession,
    *,
    member_id: str,
    payload: dict[str, Any],
) -> tuple[uuid.UUID | None, bool]:
    """Persist a credential-free event receipt. Returns (id, created)."""
    event_key, payload_hash = event_fingerprint(payload)
    status = "ignored" if is_self_originated_event(payload) else "received"
    event_name = str(payload.get("event", "UNKNOWN"))[:100].upper()
    statement = (
        insert(BitrixInboundEvent)
        .values(
            id=uuid.uuid4(),
            member_id=member_id,
            event_key=event_key,
            event_name=event_name,
            payload_hash=payload_hash,
            status=status,
        )
        .on_conflict_do_nothing(constraint="uq_bitrix_inbound_events_key")
        .returning(BitrixInboundEvent.id)
    )
    event_id = await db.scalar(statement)
    await db.commit()
    return event_id, event_id is not None


async def enqueue_outbox_operation(
    db: AsyncSession,
    *,
    member_id: str,
    operation_key: str,
    local_entity_type: str,
    local_entity_id: uuid.UUID,
    bitrix_method: str,
    payload: dict[str, Any],
    correlation_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID | None, bool]:
    """Enqueue once; retries by callers cannot create duplicate work."""
    if not operation_key.strip() or len(operation_key) > 160:
        raise ValueError("operation_key must contain 1-160 characters")
    if not bitrix_method.strip() or len(bitrix_method) > 100:
        raise ValueError("bitrix_method must contain 1-100 characters")
    operation_id = uuid.uuid4()
    statement = (
        insert(BitrixOutboxOperation)
        .values(
            id=operation_id,
            member_id=member_id,
            operation_key=operation_key,
            local_entity_type=local_entity_type,
            local_entity_id=local_entity_id,
            bitrix_method=bitrix_method,
            payload=payload,
            correlation_id=correlation_id or uuid.uuid4(),
            max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
        )
        .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        .returning(BitrixOutboxOperation.id)
    )
    created_id = await db.scalar(statement)
    await db.commit()
    return created_id, created_id is not None


def retry_delay_seconds(attempt: int) -> int:
    exponent = max(0, attempt - 1)
    return min(
        settings.BITRIX_RETRY_BASE_SECONDS * (2**exponent),
        settings.BITRIX_RETRY_MAX_SECONDS,
    )


def is_transient_error(exc: Bitrix24Error) -> bool:
    return exc.code.upper() in _TRANSIENT_ERROR_CODES or (exc.status_code is not None and exc.status_code >= 500)


def _safe_result_reference(result: Any) -> str | None:
    candidate: Any = result
    if isinstance(result, dict):
        candidate = result.get("id") or result.get("ID")
        if candidate is None and isinstance(result.get("task"), dict):
            candidate = result["task"].get("id") or result["task"].get("ID")
        if candidate is None and isinstance(result.get("item"), dict):
            candidate = result["item"].get("id") or result["item"].get("ID")
    if isinstance(candidate, str | int):
        text = str(candidate)
        return text[:100] if text else None
    return None


async def _access_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


async def claim_outbox_batch(db: AsyncSession, *, limit: int | None = None) -> list[BitrixOutboxOperation]:
    now = datetime.now(UTC)
    batch_size = limit or settings.BITRIX_OUTBOX_BATCH_SIZE
    statement = (
        select(BitrixOutboxOperation)
        .where(
            BitrixOutboxOperation.status.in_(("pending", "retry")),
            or_(
                BitrixOutboxOperation.next_attempt_at.is_(None),
                BitrixOutboxOperation.next_attempt_at <= now,
            ),
        )
        .order_by(BitrixOutboxOperation.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    operations = list((await db.scalars(statement)).all())
    for operation in operations:
        operation.status = "processing"
        operation.locked_at = now
        if operation.local_entity_type == PARTNER_ENTITY_TYPE:
            partner = await db.get(Partner, operation.local_entity_id)
            if partner is not None:
                partner.bitrix_sync_status = "processing"
    await db.commit()
    return operations


async def process_outbox_operation(db: AsyncSession, operation: BitrixOutboxOperation) -> bool:
    installation = await db.get(BitrixInstallation, operation.member_id)
    if installation is None:
        operation.status = "failed"
        operation.error_code = "INSTALLATION_NOT_FOUND"
        operation.attempts += 1
        await _update_partner_failure(db, operation, retrying=False)
        await db.commit()
        return False

    try:
        access_token = await _access_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, access_token) as client:
            try:
                result = await client.call(operation.bitrix_method, operation.payload)
            except Bitrix24Error as exc:
                if exc.code.lower() not in {"expired_token", "invalid_token"}:
                    raise
                access_token = await refresh_installation_tokens(db, installation)
                async with Bitrix24Client(installation.client_endpoint, access_token) as retry_client:
                    result = await retry_client.call(operation.bitrix_method, operation.payload)
    except Bitrix24Error as exc:
        operation.attempts += 1
        operation.error_code = exc.code[:100]
        operation.locked_at = None
        if is_transient_error(exc) and operation.attempts < operation.max_attempts:
            operation.status = "retry"
            operation.next_attempt_at = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds(operation.attempts))
        else:
            operation.status = "failed"
        await _update_partner_failure(db, operation, retrying=operation.status == "retry")
        await db.commit()
        logger.warning(
            "bitrix_outbox_operation_failed",
            operation_id=str(operation.id),
            method=operation.bitrix_method,
            error_code=exc.code,
            retrying=operation.status == "retry",
        )
        return False

    operation.status = "completed"
    operation.attempts += 1
    operation.error_code = None
    operation.next_attempt_at = None
    operation.locked_at = None
    operation.completed_at = datetime.now(UTC)
    operation.result_reference = _safe_result_reference(result)
    await _complete_partner_projection(db, operation)
    await db.commit()
    logger.info(
        "bitrix_outbox_operation_completed",
        operation_id=str(operation.id),
        method=operation.bitrix_method,
    )
    return True


async def _update_partner_failure(
    db: AsyncSession,
    operation: BitrixOutboxOperation,
    *,
    retrying: bool,
) -> None:
    if operation.local_entity_type != PARTNER_ENTITY_TYPE:
        return
    partner = await db.get(Partner, operation.local_entity_id)
    if partner is None:
        return
    partner.bitrix_sync_status = "pending" if retrying else "failed"
    partner.bitrix_sync_error_code = operation.error_code


async def _complete_partner_projection(db: AsyncSession, operation: BitrixOutboxOperation) -> None:
    if operation.local_entity_type != PARTNER_ENTITY_TYPE:
        return
    partner = await db.get(Partner, operation.local_entity_id)
    remote_id = operation.result_reference
    if partner is None or not remote_id:
        if partner is not None:
            partner.bitrix_sync_status = "failed"
            partner.bitrix_sync_error_code = "REMOTE_ID_MISSING"
        operation.status = "failed"
        operation.error_code = "REMOTE_ID_MISSING"
        operation.completed_at = None
        return

    now = datetime.now(UTC)
    statement = (
        insert(BitrixEntityMap)
        .values(
            id=uuid.uuid4(),
            member_id=operation.member_id,
            local_entity_type=PARTNER_ENTITY_TYPE,
            local_entity_id=partner.id,
            bitrix_entity_type=f"crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}",
            bitrix_entity_id=remote_id,
            sync_version=1,
            last_synced_at=now,
            last_verified_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_bitrix_entity_maps_local",
            set_={
                "bitrix_entity_id": remote_id,
                "last_synced_at": now,
                "last_verified_at": now,
            },
        )
    )
    await db.execute(statement)
    partner.bitrix_partner_item_id = remote_id
    partner.bitrix_sync_status = "synced"
    partner.bitrix_sync_error_code = None
    partner.bitrix_synced_at = now
    if partner.bitrix_collab_status == "not_linked":
        partner.bitrix_collab_status = "binding_required"


async def release_stale_operations(db: AsyncSession) -> int:
    threshold = datetime.now(UTC) - timedelta(minutes=settings.BITRIX_PROCESSING_STALE_MINUTES)
    result = await db.execute(
        update(BitrixOutboxOperation)
        .where(
            BitrixOutboxOperation.status == "processing",
            BitrixOutboxOperation.locked_at < threshold,
        )
        .values(status="retry", locked_at=None, next_attempt_at=datetime.now(UTC), error_code="STALE_LOCK")
        .returning(BitrixOutboxOperation.id)
    )
    released = len(result.all())
    await db.commit()
    return released
