from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.settings import SystemSetting
from app.models.task import Task

TASK_ENTITY_TYPE = "task"
TASK_CREATE_METHOD = "tasks.task.add"
TASK_UPDATE_EVENT = "ONTASKUPDATE"
TASK_EVENT_HANDLER = "https://finzdorovie.ru/api/v1/integrations/bitrix24/handler"
TASK_XML_PREFIX = "partner_cabinet:"
TASK_RESPONSIBLE_SETTING_PREFIX = "bitrix_task_responsible_"
TASK_CREATOR_SETTING = "bitrix_task_creator_id"

_PRIORITY_TO_BITRIX = {"low": "0", "medium": "1", "high": "2"}
_STATUS_FROM_BITRIX = {"2": "pending", "3": "in_progress", "4": "in_progress", "5": "completed", "6": "pending"}


async def _setting_user_id(db: AsyncSession, key: str) -> int | None:
    setting = await db.get(SystemSetting, key)
    value = setting.value.strip() if setting else ""
    return int(value) if value.isdigit() and int(value) > 0 else None


async def configured_responsible_id(db: AsyncSession, assigned_to: str) -> int | None:
    return await _setting_user_id(db, f"{TASK_RESPONSIBLE_SETTING_PREFIX}{assigned_to}")


def build_task_create_payload(
    task: Task,
    *,
    deal_id: str,
    responsible_id: int,
    creator_id: int | None,
) -> dict[str, Any]:
    deadline = datetime.combine(task.due_date, time(23, 59), tzinfo=ZoneInfo("Europe/Moscow"))
    fields: dict[str, Any] = {
        "TITLE": task.title,
        "RESPONSIBLE_ID": responsible_id,
        "DEADLINE": deadline.isoformat(),
        "PRIORITY": _PRIORITY_TO_BITRIX.get(task.priority, "1"),
        "UF_CRM_TASK": [f"D_{deal_id}"],
        "XML_ID": f"{TASK_XML_PREFIX}{task.id}",
    }
    if task.description:
        fields["DESCRIPTION"] = task.description
    if creator_id:
        fields["CREATED_BY"] = creator_id
    return {"fields": fields}


async def _has_task_mapping(db: AsyncSession, task_id: uuid.UUID, member_id: str) -> bool:
    return (
        await db.scalar(
            select(BitrixEntityMap.id).where(
                BitrixEntityMap.member_id == member_id,
                BitrixEntityMap.local_entity_type == TASK_ENTITY_TYPE,
                BitrixEntityMap.local_entity_id == task_id,
            )
        )
        is not None
    )


async def schedule_task_creation(db: AsyncSession, task: Task, *, retry: bool = False) -> bool:
    installation = await active_installation(db)
    if installation is None:
        task.bitrix_sync_status = "not_scheduled"
        task.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND"
        return False
    if task.bitrix_task_id or await _has_task_mapping(db, task.id, installation.member_id):
        task.bitrix_sync_status = "synced"
        task.bitrix_sync_error_code = None
        return False

    client = await db.get(Client, task.client_id)
    if client is None or not client.bitrix_deal_id:
        task.bitrix_sync_status = "pending"
        task.bitrix_sync_error_code = "CLIENT_NOT_SYNCED"
        task.bitrix_sync_requested_at = datetime.now(UTC)
        await db.flush()
        return False

    responsible_id = await configured_responsible_id(db, task.assigned_to)
    if responsible_id is None:
        task.bitrix_sync_status = "not_scheduled"
        task.bitrix_sync_error_code = "RESPONSIBLE_NOT_CONFIGURED"
        await db.flush()
        return False

    creator_id = await _setting_user_id(db, TASK_CREATOR_SETTING)
    operation_key = f"task:create:{task.id}:v1"
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
                local_entity_type=TASK_ENTITY_TYPE,
                local_entity_id=task.id,
                bitrix_method=TASK_CREATE_METHOD,
                payload=build_task_create_payload(
                    task,
                    deal_id=client.bitrix_deal_id,
                    responsible_id=responsible_id,
                    creator_id=creator_id,
                ),
                correlation_id=uuid.uuid4(),
                max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        )

    task.bitrix_sync_status = "pending"
    task.bitrix_sync_error_code = None
    task.bitrix_sync_requested_at = datetime.now(UTC)
    await db.flush()
    return True


def extract_task_event_reference(event_name: str, payload: dict[str, Any]) -> str | None:
    if event_name.upper() != TASK_UPDATE_EVENT:
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        after = data.get("FIELDS_AFTER") or data.get("fields_after")
        if isinstance(after, dict) and (after.get("ID") or after.get("id")):
            return str(after.get("ID") or after.get("id"))
    for key in ("data[FIELDS_AFTER][ID]", "data[fields_after][id]"):
        if payload.get(key):
            return str(payload[key])
    return None


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


def _parse_closed_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


async def process_task_status_event(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    receipt.status = "processing"
    receipt.error_code = None
    await db.flush()
    if receipt.remote_entity_type != TASK_ENTITY_TYPE or not receipt.remote_entity_id:
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        return True
    mapping = await db.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == receipt.member_id,
            BitrixEntityMap.local_entity_type == TASK_ENTITY_TYPE,
            BitrixEntityMap.bitrix_entity_id == receipt.remote_entity_id,
        )
    )
    if mapping is None:
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        return True
    task = await db.get(Task, mapping.local_entity_id)
    installation = await db.get(BitrixInstallation, receipt.member_id)
    if task is None or installation is None:
        receipt.status = "failed"
        receipt.error_code = "LOCAL_REFERENCE_NOT_FOUND"
        receipt.attempts += 1
        return False

    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            result = await remote.call(
                "tasks.task.get",
                {"taskId": receipt.remote_entity_id, "select": ["ID", "STATUS", "CLOSED_DATE"]},
            )
    except Bitrix24Error as exc:
        receipt.status = "failed"
        receipt.error_code = exc.code[:100]
        receipt.attempts += 1
        return False

    remote_task = result.get("task", {}) if isinstance(result, dict) else {}
    status_value = remote_task.get("status") or remote_task.get("STATUS")
    local_status = _STATUS_FROM_BITRIX.get(str(status_value))
    if local_status is None:
        receipt.status = "failed"
        receipt.error_code = "UNSUPPORTED_TASK_STATUS"
        receipt.attempts += 1
        return False
    task.status = local_status
    task.completed_at = (
        _parse_closed_at(remote_task.get("closedDate") or remote_task.get("CLOSED_DATE")) or datetime.now(UTC)
        if local_status == "completed"
        else None
    )
    mapping.last_verified_at = datetime.now(UTC)
    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = datetime.now(UTC)
    receipt.attempts += 1
    return True


async def retry_task_status_events(db: AsyncSession, *, limit: int = 25) -> tuple[int, int]:
    receipts = list(
        (
            await db.scalars(
                select(BitrixInboundEvent)
                .where(
                    BitrixInboundEvent.remote_entity_type == TASK_ENTITY_TYPE,
                    BitrixInboundEvent.status.in_(("received", "failed")),
                    BitrixInboundEvent.attempts < settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
                )
                .order_by(BitrixInboundEvent.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    completed = 0
    for receipt in receipts:
        if await process_task_status_event(db, receipt):
            completed += 1
    await db.commit()
    return len(receipts), completed
