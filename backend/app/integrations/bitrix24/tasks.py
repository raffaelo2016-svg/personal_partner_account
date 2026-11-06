from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime, time, timedelta
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
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
from app.models.partner import Partner
from app.models.settings import SystemSetting
from app.models.task import Task
from app.models.user import User

TASK_ENTITY_TYPE = "task"
TASK_CREATE_METHOD = "tasks.task.add"
TASK_ADD_EVENT = "ONTASKADD"
TASK_UPDATE_EVENT = "ONTASKUPDATE"
TASK_EVENT_HANDLER = "https://finzdorovie.ru/api/v1/integrations/bitrix24/handler"
TASK_XML_PREFIX = "partner_cabinet:"
TASK_RESPONSIBLE_SETTING_PREFIX = "bitrix_task_responsible_"
TASK_CREATOR_SETTING = "bitrix_task_creator_id"
TASK_AUDITORS_SETTING = "bitrix_task_auditor_ids"
TASK_PARTNER_TAG = "ЛКП"
MOSCOW = ZoneInfo("Europe/Moscow")

_PRIORITY_TO_BITRIX = {"low": "0", "medium": "1", "high": "2"}
_STATUS_FROM_BITRIX = {"2": "pending", "3": "in_progress", "4": "in_progress", "5": "completed", "6": "pending"}
_NAMED_STATUS_FROM_BITRIX = {
    "pending": "pending",
    "in_progress": "in_progress",
    "supposedly_completed": "in_progress",
    "completed": "completed",
    "deferred": "pending",
    "declined": "pending",
}
_PRIORITY_FROM_BITRIX = {
    "0": "low",
    "1": "medium",
    "2": "high",
    "low": "low",
    "average": "medium",
    "high": "high",
}
_TASK_STATUS_VALUES = {"pending", "in_progress", "completed"}
_TASK_SELECT_FIELDS = [
    "ID",
    "TITLE",
    "DESCRIPTION",
    "STATUS",
    "PRIORITY",
    "DEADLINE",
    "CLOSED_DATE",
    "RESPONSIBLE_ID",
    "XML_ID",
    "UF_CRM_TASK",
    "TAGS",
]


async def _setting_user_id(db: AsyncSession, key: str) -> int | None:
    setting = await db.get(SystemSetting, key)
    value = setting.value.strip() if setting else ""
    return int(value) if value.isdigit() and int(value) > 0 else None


def _parse_user_ids(value: str) -> list[int]:
    result: list[int] = []
    for item in value.replace(",", " ").split():
        if not item.isdigit() or int(item) <= 0:
            continue
        user_id = int(item)
        if user_id not in result:
            result.append(user_id)
    return result


async def configured_auditor_ids(db: AsyncSession) -> list[int]:
    setting = await db.get(SystemSetting, TASK_AUDITORS_SETTING)
    return _parse_user_ids(setting.value if setting else "")


async def configured_responsible_id(db: AsyncSession, assigned_to: str) -> int | None:
    responsible_id = await _setting_user_id(db, f"{TASK_RESPONSIBLE_SETTING_PREFIX}{assigned_to}")
    if responsible_id is None and assigned_to == "uritech":
        # The setup CLI historically stored the internal team mapping under
        # ``admin``, while the cabinet API and UI use ``uritech``.
        return await _setting_user_id(db, f"{TASK_RESPONSIBLE_SETTING_PREFIX}admin")
    return responsible_id


def build_task_create_payload(
    task: Task,
    *,
    deal_id: str | None = None,
    partner_item_id: str | None = None,
    responsible_id: int,
    creator_id: int | None,
    auditor_ids: list[int] | None = None,
) -> dict[str, Any]:
    deadline = task.due_at
    if deadline is None and task.due_date is not None:
        deadline = datetime.combine(task.due_date, time.max, tzinfo=MOSCOW)
    references = [f"D_{deal_id}"] if deal_id else []
    if partner_item_id:
        references.append(f"T{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID:x}_{partner_item_id}")
    fields: dict[str, Any] = {
        "TITLE": task.title,
        "RESPONSIBLE_ID": responsible_id,
        "PRIORITY": _PRIORITY_TO_BITRIX.get(task.priority, "1"),
        "UF_CRM_TASK": references,
        "XML_ID": f"{TASK_XML_PREFIX}{task.id}",
        "TAGS": [TASK_PARTNER_TAG],
    }
    if deadline is not None:
        fields["DEADLINE"] = deadline.astimezone(MOSCOW).isoformat()
    if task.description:
        fields["DESCRIPTION"] = task.description
    if creator_id:
        fields["CREATED_BY"] = creator_id
    if auditor_ids:
        fields["AUDITORS"] = auditor_ids
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

    client = await db.get(Client, task.client_id) if task.client_id else None
    partner_id = task.partner_id or (client.partner_id if client else None)
    partner = await db.get(Partner, partner_id) if partner_id else None
    waiting_for_client = bool(task.client_id) and (client is None or not client.bitrix_deal_id)
    waiting_for_partner = not task.client_id and (partner is None or not partner.bitrix_partner_item_id)
    if waiting_for_client or waiting_for_partner:
        task.bitrix_sync_status = "pending"
        task.bitrix_sync_error_code = "CLIENT_NOT_SYNCED" if waiting_for_client else "PARTNER_NOT_SYNCED"
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
    auditor_ids = await configured_auditor_ids(db)
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
                    deal_id=client.bitrix_deal_id if client else None,
                    partner_item_id=partner.bitrix_partner_item_id if partner and not client else None,
                    responsible_id=responsible_id,
                    creator_id=creator_id,
                    auditor_ids=auditor_ids,
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


async def refresh_task_create_payload(db: AsyncSession, operation: BitrixOutboxOperation) -> None:
    """Build from current data at send time, so queued deadline edits are retained."""
    task = await db.get(Task, operation.local_entity_id, with_for_update=True, populate_existing=True)
    if task is None:
        raise Bitrix24Error("LOCAL_REFERENCE_NOT_FOUND", "Task no longer exists")
    client = await db.get(Client, task.client_id) if task.client_id else None
    partner_id = task.partner_id or (client.partner_id if client else None)
    partner = await db.get(Partner, partner_id) if partner_id else None
    if task.client_id and (client is None or not client.bitrix_deal_id):
        raise Bitrix24Error("CLIENT_NOT_SYNCED", "Task client is not synchronized")
    if not task.client_id and (partner is None or not partner.bitrix_partner_item_id):
        raise Bitrix24Error("PARTNER_NOT_SYNCED", "Task partner is not synchronized")
    responsible_id = await configured_responsible_id(db, task.assigned_to)
    if responsible_id is None:
        raise Bitrix24Error("RESPONSIBLE_NOT_CONFIGURED", "Task responsible is not configured")
    operation.payload = build_task_create_payload(
        task,
        deal_id=client.bitrix_deal_id if client else None,
        partner_item_id=partner.bitrix_partner_item_id if partner and not client else None,
        responsible_id=responsible_id,
        creator_id=await _setting_user_id(db, TASK_CREATOR_SETTING),
        auditor_ids=await configured_auditor_ids(db),
    )


def task_status_methods(current_status: str, target_status: str) -> list[str]:
    """Return the Bitrix24 task actions needed for one cabinet transition."""
    if current_status == target_status:
        return []
    if target_status not in _TASK_STATUS_VALUES:
        raise ValueError("Unsupported task status")
    if target_status == "completed":
        return ["tasks.task.complete"]
    if current_status == "completed":
        methods = ["tasks.task.renew"]
        if target_status == "in_progress":
            methods.append("tasks.task.start")
        return methods
    if target_status == "in_progress":
        return ["tasks.task.start"]
    return ["tasks.task.pause"]


async def sync_task_status(db: AsyncSession, task: Task, target_status: str) -> None:
    """Apply a cabinet status transition to an already linked Bitrix24 task."""
    if not task.bitrix_task_id:
        return
    methods = task_status_methods(task.status, target_status)
    if not methods:
        return
    installation = await active_installation(db)
    if installation is None:
        raise Bitrix24Error("INSTALLATION_NOT_FOUND", "Active Bitrix24 installation not found")
    access_token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, access_token) as client:
        for method in methods:
            await client.call(method, {"taskId": task.bitrix_task_id})

    now = datetime.now(UTC)
    task.bitrix_sync_status = "synced"
    task.bitrix_sync_error_code = None
    task.bitrix_sync_requested_at = now
    task.bitrix_synced_at = now


async def sync_task_fields(db: AsyncSession, task: Task, updates: dict[str, Any]) -> None:
    """Apply cabinet edits to the linked task before accepting them locally."""
    if not task.bitrix_task_id:
        return
    fields: dict[str, Any] = {}
    for local_name, remote_name in (("title", "TITLE"), ("description", "DESCRIPTION")):
        if local_name in updates:
            fields[remote_name] = updates[local_name] or ""
    if "priority" in updates:
        fields["PRIORITY"] = _PRIORITY_TO_BITRIX.get(updates["priority"], "1")
    if "due_at" in updates or "due_date" in updates:
        due_at = updates.get("due_at", task.due_at)
        due_date = updates.get("due_date", task.due_date)
        if due_at is None and due_date is not None:
            due_at = datetime.combine(due_date, time.max, tzinfo=MOSCOW)
        fields["DEADLINE"] = due_at.astimezone(MOSCOW).isoformat() if due_at else ""
    if "assigned_to" in updates:
        responsible_id = await configured_responsible_id(db, updates["assigned_to"])
        if responsible_id is None:
            raise Bitrix24Error("RESPONSIBLE_NOT_CONFIGURED", "Task responsible is not configured")
        fields["RESPONSIBLE_ID"] = responsible_id
    if not fields:
        return
    installation = await active_installation(db)
    if installation is None:
        raise Bitrix24Error("INSTALLATION_NOT_FOUND", "Active Bitrix24 installation not found")
    token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, token) as remote:
        await remote.call("tasks.task.update", {"taskId": task.bitrix_task_id, "fields": fields})
    now = datetime.now(UTC)
    task.bitrix_sync_status = "synced"
    task.bitrix_sync_error_code = None
    task.bitrix_sync_requested_at = now
    task.bitrix_synced_at = now


def extract_task_event_reference(event_name: str, payload: dict[str, Any]) -> str | None:
    if event_name.upper() not in {TASK_ADD_EVENT, TASK_UPDATE_EVENT}:
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


def _remote_field(remote_task: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in remote_task:
            return remote_task[name]
    return None


def _remote_deal_id(remote_task: dict[str, Any]) -> str | None:
    values = _remote_field(remote_task, "ufCrmTask", "UF_CRM_TASK", "crmItemIds") or []
    if isinstance(values, dict):
        values = list(values.values())
    if isinstance(values, str):
        values = [values]
    for value in values if isinstance(values, list) else []:
        reference = str(value).strip().upper()
        if reference.startswith("D_") and reference[2:].isdigit():
            return reference[2:]
    return None


def _parse_due_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid Bitrix24 deadline") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MOSCOW)
    return parsed.astimezone(UTC)


def _parse_due_date(value: Any) -> date | None:
    due_at = _parse_due_at(value)
    return due_at.astimezone(MOSCOW).date() if due_at else None


def _has_partner_tag(remote_task: dict[str, Any]) -> bool:
    tags = _remote_field(remote_task, "tags", "TAGS") or []
    if isinstance(tags, dict):
        tags = list(tags.values())
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        return False
    return any(
        str(tag.get("title") or tag.get("name") or "" if isinstance(tag, dict) else tag).strip().casefold()
        == TASK_PARTNER_TAG.casefold()
        for tag in tags
    )


async def _remote_task_target(
    db: AsyncSession, remote_task: dict[str, Any]
) -> tuple[Partner | None, Client | None, str | None]:
    """Resolve every CRM link; never pick an arbitrary partner from several links."""
    values = _remote_field(remote_task, "ufCrmTask", "UF_CRM_TASK", "crmItemIds") or []
    if isinstance(values, dict):
        values = list(values.values())
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return None, None, "CRM_REFERENCE_REQUIRED"
    partner_prefix = f"T{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID:x}_".upper()
    deal_ids: set[str] = set()
    partner_item_ids: set[str] = set()
    for value in values:
        reference = str(value).strip().upper()
        if reference.startswith("D_") and reference[2:].isdigit():
            deal_ids.add(reference[2:])
        elif reference.startswith(partner_prefix) and reference[len(partner_prefix) :].isdigit():
            partner_item_ids.add(reference[len(partner_prefix) :])
    if not deal_ids and not partner_item_ids:
        return None, None, "CRM_REFERENCE_REQUIRED"
    clients = (
        list(
            (
                await db.scalars(select(Client).where(Client.bitrix_deal_id.in_(deal_ids), Client.deleted_at.is_(None)))
            ).all()
        )
        if deal_ids
        else []
    )
    if len(clients) != len(deal_ids):
        return None, None, "CLIENT_NOT_FOUND"
    partners = (
        list(
            (
                await db.scalars(
                    select(Partner).where(
                        Partner.bitrix_partner_item_id.in_(partner_item_ids), Partner.deleted_at.is_(None)
                    )
                )
            ).all()
        )
        if partner_item_ids
        else []
    )
    if len(partners) != len(partner_item_ids):
        return None, None, "PARTNER_NOT_FOUND"
    partner_ids = {client.partner_id for client in clients} | {partner.id for partner in partners}
    if len(partner_ids) != 1:
        return None, None, "AMBIGUOUS_TASK_PARTNER"
    partner = partners[0] if partners else await db.get(Partner, next(iter(partner_ids)))
    if partner is None or partner.deleted_at is not None:
        return None, None, "PARTNER_NOT_FOUND"
    return partner, clients[0] if len(clients) == 1 else None, None


def _mark_task_event_failure(receipt: BitrixInboundEvent, code: str) -> bool:
    receipt.status = "failed"
    receipt.error_code = code[:100]
    receipt.attempts += 1
    return False


async def _responsible_role(db: AsyncSession, remote_task: dict[str, Any], fallback: str) -> str:
    value = _remote_field(remote_task, "responsibleId", "RESPONSIBLE_ID")
    try:
        responsible_id = int(value)
    except (TypeError, ValueError):
        return fallback

    # Preserve the cabinet role when several roles intentionally point to the
    # same Bitrix user.  Otherwise a task assigned to URITECH can be moved to
    # the partner tab merely because the partner mapping is checked first.
    if fallback in {"partner", "uritech"} and await configured_responsible_id(db, fallback) == responsible_id:
        return fallback
    for role in ("partner", "uritech"):
        if await configured_responsible_id(db, role) == responsible_id:
            return role
    return fallback


async def _apply_remote_task_fields(db: AsyncSession, task: Task, remote_task: dict[str, Any]) -> bool:
    partner = client = None
    if task.bitrix_imported:
        if not _has_partner_tag(remote_task):
            task.bitrix_published = False
            task.bitrix_sync_status = "failed"
            task.bitrix_sync_error_code = "TASK_NOT_PUBLISHED"
            return False
        partner, client, error_code = await _remote_task_target(db, remote_task)
        if error_code:
            task.bitrix_published = False
            task.bitrix_sync_status = "failed"
            task.bitrix_sync_error_code = error_code
            return False
    title = str(_remote_field(remote_task, "title", "TITLE") or "").strip()
    status_value = str(_remote_field(remote_task, "status", "STATUS") or "").lower()
    status = _STATUS_FROM_BITRIX.get(status_value) or _NAMED_STATUS_FROM_BITRIX.get(status_value)
    if not title or status is None:
        return False

    description_value = _remote_field(remote_task, "description", "DESCRIPTION")
    priority_value = str(_remote_field(remote_task, "priority", "PRIORITY") or "1").lower()
    deadline_value = _remote_field(remote_task, "deadline", "DEADLINE")
    try:
        due_at = _parse_due_at(deadline_value)
    except ValueError:
        return False
    now = datetime.now(UTC)
    task.title = title[:255]
    task.description = unescape(str(description_value)).strip() if description_value else None
    task.status = status
    task.priority = _PRIORITY_FROM_BITRIX.get(priority_value, "medium")
    task.assigned_to = "partner" if task.bitrix_imported else await _responsible_role(db, remote_task, task.assigned_to)
    if partner is not None:
        task.partner_id = partner.id
        task.client_id = client.id if client else None
        task.bitrix_published = True
    task.due_at = due_at
    task.due_date = due_at.astimezone(MOSCOW).date() if due_at else None
    task.completed_at = (
        _parse_closed_at(_remote_field(remote_task, "closedDate", "CLOSED_DATE")) or now
        if status == "completed"
        else None
    )
    task.bitrix_sync_status = "synced"
    task.bitrix_sync_error_code = None
    task.bitrix_synced_at = now
    return True


async def _import_remote_task(
    db: AsyncSession,
    *,
    receipt: BitrixInboundEvent,
    remote_task: dict[str, Any],
    installation: BitrixInstallation,
) -> bool:
    xml_id = str(_remote_field(remote_task, "xmlId", "XML_ID") or "").strip()
    if xml_id.startswith(TASK_XML_PREFIX):
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        receipt.attempts += 1
        return True

    if not _has_partner_tag(remote_task):
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        receipt.attempts += 1
        return True

    partner, client, error_code = await _remote_task_target(db, remote_task)
    if error_code:
        return _mark_task_event_failure(receipt, error_code)
    assert partner is not None

    title = str(_remote_field(remote_task, "title", "TITLE") or "").strip()
    if not title:
        return _mark_task_event_failure(receipt, "TASK_TITLE_REQUIRED")
    title = title[:255]
    description_value = _remote_field(remote_task, "description", "DESCRIPTION")
    description = unescape(str(description_value)).strip() if description_value else None
    status_value = str(_remote_field(remote_task, "status", "STATUS") or "2").lower()
    status = _STATUS_FROM_BITRIX.get(status_value) or _NAMED_STATUS_FROM_BITRIX.get(status_value)
    if status is None:
        return _mark_task_event_failure(receipt, "UNSUPPORTED_TASK_STATUS")
    priority_value = str(_remote_field(remote_task, "priority", "PRIORITY") or "1").lower()
    priority = _PRIORITY_FROM_BITRIX.get(priority_value, "medium")
    try:
        due_at = _parse_due_at(_remote_field(remote_task, "deadline", "DEADLINE"))
    except ValueError:
        return _mark_task_event_failure(receipt, "INVALID_TASK_DEADLINE")
    creator_id = await db.scalar(select(User.id).where(User.role == "admin", User.is_active.is_(True)).limit(1))
    now = datetime.now(UTC)
    task = Task(
        client_id=client.id if client else None,
        partner_id=partner.id,
        title=title,
        description=description,
        status=status,
        priority=priority,
        assigned_to="partner",
        created_by=creator_id or partner.user_id,
        due_date=due_at.astimezone(MOSCOW).date() if due_at else None,
        due_at=due_at,
        bitrix_imported=True,
        completed_at=(
            _parse_closed_at(_remote_field(remote_task, "closedDate", "CLOSED_DATE")) or now
            if status == "completed"
            else None
        ),
        bitrix_sync_status="synced",
        bitrix_task_id=receipt.remote_entity_id,
        bitrix_synced_at=now,
    )
    db.add(task)
    await db.flush()
    db.add(
        BitrixEntityMap(
            member_id=installation.member_id,
            local_entity_type=TASK_ENTITY_TYPE,
            local_entity_id=task.id,
            bitrix_entity_type=TASK_ENTITY_TYPE,
            bitrix_entity_id=receipt.remote_entity_id,
            last_synced_at=now,
            last_verified_at=now,
        )
    )
    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = now
    receipt.attempts += 1
    return True


async def process_task_status_event(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    receipt.status = "processing"
    receipt.error_code = None
    await db.flush()
    if receipt.remote_entity_type != TASK_ENTITY_TYPE or not receipt.remote_entity_id:
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        return True
    installation = await db.scalar(
        select(BitrixInstallation).where(BitrixInstallation.member_id == receipt.member_id).with_for_update()
    )
    if installation is None:
        return _mark_task_event_failure(receipt, "INSTALLATION_NOT_FOUND")
    mapping = await db.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == receipt.member_id,
            BitrixEntityMap.local_entity_type == TASK_ENTITY_TYPE,
            BitrixEntityMap.bitrix_entity_id == receipt.remote_entity_id,
        )
    )
    task = await db.get(Task, mapping.local_entity_id) if mapping is not None else None
    if mapping is not None and task is None:
        return _mark_task_event_failure(receipt, "LOCAL_REFERENCE_NOT_FOUND")

    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            result = await remote.call(
                "tasks.task.get",
                {
                    "taskId": receipt.remote_entity_id,
                    "select": _TASK_SELECT_FIELDS,
                },
            )
    except Bitrix24Error as exc:
        receipt.status = "failed"
        receipt.error_code = exc.code[:100]
        receipt.attempts += 1
        return False

    remote_task = result.get("task", {}) if isinstance(result, dict) else {}
    if mapping is None:
        return await _import_remote_task(
            db,
            receipt=receipt,
            remote_task=remote_task,
            installation=installation,
        )

    assert task is not None
    if not await _apply_remote_task_fields(db, task, remote_task):
        receipt.status = "failed"
        receipt.error_code = "INVALID_REMOTE_TASK"
        receipt.attempts += 1
        return False
    mapping.last_synced_at = datetime.now(UTC)
    mapping.last_verified_at = datetime.now(UTC)
    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = datetime.now(UTC)
    receipt.attempts += 1
    return True


async def reconcile_remote_task(db: AsyncSession, *, task_id: uuid.UUID) -> bool:
    """Refresh one explicitly selected mapped task from Bitrix24."""
    installation = await active_installation(db)
    if installation is None:
        return False
    mapping = await db.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == installation.member_id,
            BitrixEntityMap.local_entity_type == TASK_ENTITY_TYPE,
            BitrixEntityMap.local_entity_id == task_id,
        )
    )
    task = await db.get(Task, task_id)
    if mapping is None or task is None:
        return False

    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            result = await remote.call(
                "tasks.task.get",
                {"taskId": mapping.bitrix_entity_id, "select": _TASK_SELECT_FIELDS},
            )
    except Bitrix24Error:
        return False

    remote_task = result.get("task", {}) if isinstance(result, dict) else {}
    if not await _apply_remote_task_fields(db, task, remote_task):
        return False
    now = datetime.now(UTC)
    mapping.last_synced_at = now
    mapping.last_verified_at = now
    await db.commit()
    return True


async def reconcile_remote_tasks(db: AsyncSession, *, limit: int = 25) -> dict[str, int]:
    """Refresh stale mapped tasks so a missed Bitrix24 event cannot leave cabinet data stale."""
    installation = await active_installation(db)
    if installation is None:
        return {"claimed": 0, "completed": 0, "failed": 0}
    stale_before = datetime.now(UTC) - timedelta(hours=settings.BITRIX_RECONCILE_AFTER_HOURS)
    published_stale_before = datetime.now(UTC) - timedelta(minutes=1)
    mappings = list(
        (
            await db.scalars(
                select(BitrixEntityMap)
                .outerjoin(Task, Task.id == BitrixEntityMap.local_entity_id)
                .where(
                    BitrixEntityMap.member_id == installation.member_id,
                    BitrixEntityMap.local_entity_type == TASK_ENTITY_TYPE,
                    or_(
                        BitrixEntityMap.last_verified_at.is_(None),
                        BitrixEntityMap.last_verified_at < stale_before,
                        and_(Task.bitrix_imported.is_(True), BitrixEntityMap.last_verified_at < published_stale_before),
                    ),
                )
                .order_by(BitrixEntityMap.last_verified_at.asc().nullsfirst(), BitrixEntityMap.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True, of=BitrixEntityMap)
            )
        ).all()
    )
    if not mappings:
        return {"claimed": 0, "completed": 0, "failed": 0}

    completed = 0
    failed = 0
    token = await _installation_token(db, installation)
    async with Bitrix24Client(installation.client_endpoint, token) as remote:
        for mapping in mappings:
            task = await db.get(Task, mapping.local_entity_id)
            if task is None:
                failed += 1
                continue
            try:
                result = await remote.call(
                    "tasks.task.get",
                    {"taskId": mapping.bitrix_entity_id, "select": _TASK_SELECT_FIELDS},
                )
            except Bitrix24Error:
                failed += 1
                continue
            remote_task = result.get("task", {}) if isinstance(result, dict) else {}
            if not await _apply_remote_task_fields(db, task, remote_task):
                failed += 1
                continue
            now = datetime.now(UTC)
            mapping.last_synced_at = now
            mapping.last_verified_at = now
            completed += 1
    await db.commit()
    return {"claimed": len(mappings), "completed": completed, "failed": failed}


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


async def discover_remote_tasks(db: AsyncSession) -> dict[str, int]:
    """Recover missed publish events using a durable, overlapping change cursor."""
    result = {"scanned": 0, "imported": 0, "updated": 0, "failed": 0}
    installation = await active_installation(db)
    if installation is None:
        return result
    installation = await db.scalar(
        select(BitrixInstallation).where(BitrixInstallation.member_id == installation.member_id).with_for_update()
    )
    assert installation is not None
    cursor_key = f"bitrix_task_discovery_{hashlib.sha256(installation.member_id.encode()).hexdigest()}"
    cursor = await db.get(SystemSetting, cursor_key)
    started_at = datetime.now(UTC)
    filters: dict[str, Any] = {"TAG": TASK_PARTNER_TAG}
    if cursor is not None:
        try:
            changed_after = _parse_due_at(cursor.value)
        except ValueError:
            changed_after = None
        if changed_after:
            filters[">=CHANGED_DATE"] = (changed_after - timedelta(minutes=5)).isoformat()
    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            remote_tasks = await remote.list_all(
                "tasks.task.list",
                {"filter": filters, "order": {"CHANGED_DATE": "asc"}, "select": [*_TASK_SELECT_FIELDS, "CHANGED_DATE"]},
                result_key="tasks",
            )
    except Bitrix24Error:
        result["failed"] = 1
        return result

    for remote_task in remote_tasks:
        if not isinstance(remote_task, dict):
            continue
        remote_id = str(_remote_field(remote_task, "id", "ID") or "")
        if not remote_id.isdigit() or not _has_partner_tag(remote_task):
            continue
        result["scanned"] += 1
        mapping = await db.scalar(
            select(BitrixEntityMap).where(
                BitrixEntityMap.member_id == installation.member_id,
                BitrixEntityMap.local_entity_type == TASK_ENTITY_TYPE,
                BitrixEntityMap.bitrix_entity_id == remote_id,
            )
        )
        if mapping is not None:
            task = await db.get(Task, mapping.local_entity_id)
            if task is not None and await _apply_remote_task_fields(db, task, remote_task):
                mapping.last_synced_at = started_at
                mapping.last_verified_at = started_at
                result["updated"] += 1
            else:
                result["failed"] += 1
            continue
        changed_at = _remote_field(remote_task, "changedDate", "CHANGED_DATE") or ""
        key = hashlib.sha256(f"task-discovery:{remote_id}:{changed_at}".encode()).hexdigest()
        receipt_id = await db.scalar(
            insert(BitrixInboundEvent)
            .values(
                id=uuid.uuid4(),
                member_id=installation.member_id,
                event_key=key,
                event_name=TASK_ADD_EVENT,
                payload_hash=key,
                remote_entity_type=TASK_ENTITY_TYPE,
                remote_entity_id=remote_id,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_inbound_events_key")
            .returning(BitrixInboundEvent.id)
        )
        if receipt_id is None:
            continue
        receipt = await db.get(BitrixInboundEvent, receipt_id)
        assert receipt is not None
        if await _import_remote_task(db, receipt=receipt, remote_task=remote_task, installation=installation):
            if receipt.status == "completed":
                result["imported"] += 1
        else:
            result["failed"] += 1
    if cursor is None:
        db.add(SystemSetting(key=cursor_key, value=started_at.isoformat()))
    else:
        cursor.value = started_at.isoformat()
    await db.commit()
    return result
