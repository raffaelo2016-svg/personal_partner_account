from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.clients import CLIENT_DEAL_ENTITY_TYPE
from app.integrations.bitrix24.oauth import refresh_installation_tokens
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.services.audit import audit_log
from app.services.s3_service import delete_file_async, download_file_async, upload_file_async
from app.validation.files import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    file_extension,
    has_valid_signature,
    mime_type_for_filename,
)

FILE_ENTITY_TYPE = "file"
FILE_CREATE_METHOD = "crm.timeline.comment.add"
FILE_MARKER_PREFIX = "partner-cabinet-file:"
TIMELINE_COMMENT_ADD_EVENT = "ONCRMTIMELINECOMMENTADD"
TIMELINE_COMMENT_ENTITY_TYPE = "timeline_comment"
TIMELINE_FILE_REMOTE_ENTITY_TYPE = "crm_timeline_file"
TIMELINE_EVENT_HANDLER = "https://finzdorovie.ru/api/v1/integrations/bitrix24/handler"
CRM_ACTIVITY_ADD_EVENT = "ONCRMACTIVITYADD"
CRM_ACTIVITY_ENTITY_TYPE = "crm_activity"
CRM_ACTIVITY_FILE_REMOTE_ENTITY_TYPE = "crm_activity_file"


def file_marker(file_id: uuid.UUID) -> str:
    return f"[{FILE_MARKER_PREFIX}{file_id}]"


def extract_timeline_comment_event_reference(event_name: str, payload: dict[str, Any]) -> str | None:
    if event_name.upper() != TIMELINE_COMMENT_ADD_EVENT:
        return None
    data = payload.get("data")
    if isinstance(data, dict) and (data.get("ID") or data.get("id")):
        return str(data.get("ID") or data.get("id"))
    for key in ("data[ID]", "data[id]"):
        if payload.get(key):
            return str(payload[key])
    return None


def extract_crm_activity_event_reference(event_name: str, payload: dict[str, Any]) -> str | None:
    if event_name.upper() != CRM_ACTIVITY_ADD_EVENT:
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        fields = data.get("FIELDS") or data.get("fields") or data
        if isinstance(fields, dict) and (fields.get("ID") or fields.get("id")):
            return str(fields.get("ID") or fields.get("id"))
    for key in ("data[FIELDS][ID]", "data[fields][id]", "data[ID]", "data[id]"):
        if payload.get(key):
            return str(payload[key])
    return None


def build_file_operation_payload(record: FileUpload, *, deal_id: str) -> dict[str, Any]:
    ext = PurePosixPath(record.s3_key).suffix.lower()
    return {
        "deal_id": str(deal_id),
        "s3_key": record.s3_key,
        "remote_name": f"document_{record.id}{ext}",
        "marker": file_marker(record.id),
    }


async def _has_file_mapping(db: AsyncSession, file_id: uuid.UUID, member_id: str) -> bool:
    return (
        await db.scalar(
            select(BitrixEntityMap.id).where(
                BitrixEntityMap.member_id == member_id,
                BitrixEntityMap.local_entity_type == FILE_ENTITY_TYPE,
                BitrixEntityMap.local_entity_id == file_id,
            )
        )
        is not None
    )


async def schedule_file_creation(db: AsyncSession, record: FileUpload, *, retry: bool = False) -> bool:
    installation = await active_installation(db)
    if installation is None:
        record.bitrix_sync_status = "not_scheduled"
        record.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND"
        return False
    if record.bitrix_timeline_comment_id or await _has_file_mapping(db, record.id, installation.member_id):
        record.bitrix_sync_status = "synced"
        record.bitrix_sync_error_code = None
        return False

    client = await db.get(Client, record.client_id)
    if client is None or not client.bitrix_deal_id:
        record.bitrix_sync_status = "pending"
        record.bitrix_sync_error_code = "CLIENT_NOT_SYNCED"
        record.bitrix_sync_requested_at = datetime.now(UTC)
        await db.flush()
        return False

    operation_key = f"file:create:{record.id}:v1"
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
                local_entity_type=FILE_ENTITY_TYPE,
                local_entity_id=record.id,
                bitrix_method=FILE_CREATE_METHOD,
                payload=build_file_operation_payload(record, deal_id=client.bitrix_deal_id),
                correlation_id=uuid.uuid4(),
                max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
            )
            .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
        )

    record.bitrix_sync_status = "pending"
    record.bitrix_sync_error_code = None
    record.bitrix_sync_requested_at = datetime.now(UTC)
    await db.flush()
    return True


def _comment_reference(comment: dict[str, Any]) -> str | None:
    comment_id = comment.get("ID") or comment.get("id")
    raw_files = comment.get("FILES") or comment.get("files") or []
    if isinstance(raw_files, dict):
        files = list(raw_files.values())
    elif isinstance(raw_files, list):
        files = raw_files
    else:
        files = []
    if not comment_id or not files:
        return None
    first = files[0]
    file_id = (first.get("ID") or first.get("id")) if isinstance(first, dict) else None
    return f"{comment_id}:{file_id}" if file_id else None


async def execute_file_creation(client: Bitrix24Client, operation: BitrixOutboxOperation) -> str:
    payload = operation.payload
    deal_id = str(payload.get("deal_id") or "")
    marker = str(payload.get("marker") or "")
    if not deal_id or not marker:
        raise Bitrix24Error("INVALID_LOCAL_PAYLOAD", "Document operation has no CRM reference")

    existing = await client.list_all(
        "crm.timeline.comment.list",
        {
            "filter": {"ENTITY_ID": deal_id, "ENTITY_TYPE": "deal"},
            "select": ["ID", "COMMENT", "FILES"],
            "order": {"ID": "DESC"},
        },
        max_pages=20,
    )
    if isinstance(existing, list):
        for comment in existing:
            if isinstance(comment, dict) and marker in str(comment.get("COMMENT") or comment.get("comment") or ""):
                reference = _comment_reference(comment)
                if reference:
                    return reference

    try:
        data = await download_file_async(str(payload.get("s3_key") or ""))
    except Exception as exc:  # noqa: BLE001
        raise Bitrix24Error("LOCAL_FILE_UNAVAILABLE", "Could not read the queued document") from exc
    result = await client.call(
        FILE_CREATE_METHOD,
        {
            "fields": {
                "ENTITY_ID": deal_id,
                "ENTITY_TYPE": "deal",
                "COMMENT": f"Документ из партнёрского кабинета\n{marker}",
                "FILES": [[str(payload.get("remote_name") or "document"), base64.b64encode(data).decode("ascii")]],
            }
        },
    )
    comment_id = result if isinstance(result, str | int) else None
    if not comment_id:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return a timeline comment ID")
    created = await client.call("crm.timeline.comment.get", {"id": comment_id})
    if not isinstance(created, dict):
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return the created document")
    reference = _comment_reference(created)
    if not reference:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return an attached Disk file ID")
    return reference


def _mark_inbound_failure(receipt: BitrixInboundEvent, code: str) -> bool:
    receipt.status = "failed"
    receipt.error_code = code[:100]
    receipt.attempts += 1
    return False


def _comment_files(comment: dict[str, Any]) -> list[dict[str, Any]]:
    raw = comment.get("FILES") or comment.get("files") or []
    values = list(raw.values()) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    return [item for item in values if isinstance(item, dict)]


def _activity_files(activity: dict[str, Any]) -> list[dict[str, Any]]:
    raw = (
        activity.get("FILES")
        or activity.get("files")
        or activity.get("STORAGE_ELEMENT_IDS")
        or activity.get("storageElementIds")
        or []
    )
    values = list(raw.values()) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    return [item if isinstance(item, dict) else {"ID": item} for item in values if item]


def _activity_deal_id(activity: dict[str, Any]) -> str | None:
    owner_type = str(activity.get("OWNER_TYPE_ID") or activity.get("ownerTypeId") or "")
    owner_id = str(activity.get("OWNER_ID") or activity.get("ownerId") or "").strip()
    if owner_type == "2" and owner_id:
        return owner_id
    bindings = activity.get("BINDINGS") or activity.get("bindings") or []
    if isinstance(bindings, dict):
        bindings = list(bindings.values())
    for binding in bindings if isinstance(bindings, list) else []:
        if not isinstance(binding, dict):
            continue
        binding_type = str(binding.get("OWNER_TYPE_ID") or binding.get("ownerTypeId") or "")
        binding_id = str(binding.get("OWNER_ID") or binding.get("ownerId") or "").strip()
        if binding_type == "2" and binding_id:
            return binding_id
    return None


def _safe_remote_name(value: Any) -> str | None:
    name = PurePosixPath(str(value or "").replace("\\", "/")).name.strip()
    if not name or len(name) > 500 or file_extension(name) not in ALLOWED_EXTENSIONS:
        return None
    return name


async def _installation_token(db: AsyncSession, installation: BitrixInstallation) -> str:
    expires_at = installation.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            return await refresh_installation_tokens(db, installation)
    return await decrypt_token(db, installation.access_token_encrypted)


async def _local_client_for_deal(db: AsyncSession, *, member_id: str, deal_id: str) -> Client | None:
    deal_mapping = await db.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == member_id,
            BitrixEntityMap.local_entity_type == CLIENT_DEAL_ENTITY_TYPE,
            BitrixEntityMap.bitrix_entity_type == "crm_deal",
            BitrixEntityMap.bitrix_entity_id == deal_id,
        )
    )
    if deal_mapping is None:
        return None
    local_client = await db.get(Client, deal_mapping.local_entity_id)
    return local_client if local_client is not None and local_client.deleted_at is None else None


async def _import_remote_files(
    db: AsyncSession,
    remote: Bitrix24Client,
    receipt: BitrixInboundEvent,
    *,
    local_client: Client,
    parent_id: str,
    files: list[dict[str, Any]],
    remote_entity_type: str,
    activity_id: str | None = None,
    comment_id: str | None = None,
) -> bool:
    for item in files:
        disk_file_id = str(item.get("id") or item.get("ID") or "").strip()
        if not disk_file_id:
            return _mark_inbound_failure(receipt, "REMOTE_FILE_ID_MISSING")
        remote_reference = f"{parent_id}:{disk_file_id}"
        existing_mapping = await db.scalar(
            select(BitrixEntityMap.id).where(
                BitrixEntityMap.member_id == receipt.member_id,
                BitrixEntityMap.bitrix_entity_type == remote_entity_type,
                BitrixEntityMap.bitrix_entity_id == remote_reference,
            )
        )
        if existing_mapping is not None:
            continue

        info = await remote.call("disk.file.get", {"id": disk_file_id})
        if not isinstance(info, dict):
            return _mark_inbound_failure(receipt, "INVALID_FILE_RESPONSE")
        name = _safe_remote_name(info.get("NAME") or info.get("name") or item.get("name"))
        if name is None:
            return _mark_inbound_failure(receipt, "UNSUPPORTED_FILE_TYPE")
        try:
            announced_size = int(info.get("SIZE") or info.get("size") or item.get("size") or 0)
        except (TypeError, ValueError):
            return _mark_inbound_failure(receipt, "INVALID_FILE_RESPONSE")
        if announced_size > MAX_FILE_SIZE_BYTES:
            return _mark_inbound_failure(receipt, "FILE_TOO_LARGE")
        download_url = str(info.get("DOWNLOAD_URL") or info.get("downloadUrl") or "")
        data = await remote.download_file(download_url, max_bytes=MAX_FILE_SIZE_BYTES)
        extension = file_extension(name)
        if not has_valid_signature(data, extension):
            return _mark_inbound_failure(receipt, "INVALID_FILE_CONTENT")
        mime_type = mime_type_for_filename(name)
        if mime_type is None:
            return _mark_inbound_failure(receipt, "UNSUPPORTED_FILE_TYPE")
        content_sha256 = hashlib.sha256(data).hexdigest()
        duplicate = await db.scalar(
            select(FileUpload.id).where(
                FileUpload.client_id == local_client.id,
                FileUpload.content_sha256 == content_sha256,
            )
        )
        if duplicate is not None:
            continue

        s3_key = await upload_file_async(data, name, mime_type)
        try:
            now = datetime.now(UTC)
            record = FileUpload(
                client_id=local_client.id,
                document_type="other",
                original_name=name,
                s3_key=s3_key,
                size=len(data),
                mime_type=mime_type,
                content_sha256=content_sha256,
                bitrix_sync_status="synced",
                bitrix_timeline_comment_id=comment_id,
                bitrix_activity_id=activity_id,
                bitrix_disk_file_id=disk_file_id,
                bitrix_synced_at=now,
            )
            db.add(record)
            await db.flush()
            db.add(
                BitrixEntityMap(
                    member_id=receipt.member_id,
                    local_entity_type=FILE_ENTITY_TYPE,
                    local_entity_id=record.id,
                    bitrix_entity_type=remote_entity_type,
                    bitrix_entity_id=remote_reference,
                    sync_version=1,
                    last_synced_at=now,
                    last_verified_at=now,
                )
            )
            await db.flush()
        except Exception:
            await delete_file_async(s3_key)
            raise
        audit_log(action="import_file_from_bitrix", target_id=str(record.id), target_type="file")
    return True


async def process_timeline_comment_add_event(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    """Import supported attachments from a known client deal into MinIO once."""
    receipt.status = "processing"
    receipt.error_code = None
    await db.flush()
    if receipt.remote_entity_type != TIMELINE_COMMENT_ENTITY_TYPE or not receipt.remote_entity_id:
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        return True

    installation = await db.get(BitrixInstallation, receipt.member_id)
    if installation is None:
        return _mark_inbound_failure(receipt, "INSTALLATION_NOT_FOUND")

    comment_id = receipt.remote_entity_id
    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            comment = await remote.call("crm.timeline.comment.get", {"id": comment_id})
            if not isinstance(comment, dict):
                return _mark_inbound_failure(receipt, "INVALID_COMMENT_RESPONSE")
            if str(comment.get("ENTITY_TYPE") or comment.get("entityType") or "").lower() != "deal":
                receipt.status = "ignored"
                receipt.processed_at = datetime.now(UTC)
                receipt.attempts += 1
                return True
            if FILE_MARKER_PREFIX in str(comment.get("COMMENT") or comment.get("comment") or ""):
                receipt.status = "ignored"
                receipt.processed_at = datetime.now(UTC)
                receipt.attempts += 1
                return True

            deal_id = str(comment.get("ENTITY_ID") or comment.get("entityId") or "").strip()
            local_client = await _local_client_for_deal(db, member_id=receipt.member_id, deal_id=deal_id)
            if local_client is None:
                return _mark_inbound_failure(receipt, "CLIENT_DEAL_NOT_FOUND")

            files = _comment_files(comment)
            if not files:
                receipt.status = "ignored"
                receipt.processed_at = datetime.now(UTC)
                receipt.attempts += 1
                return True

            if not await _import_remote_files(
                db,
                remote,
                receipt,
                local_client=local_client,
                parent_id=comment_id,
                files=files,
                remote_entity_type=TIMELINE_FILE_REMOTE_ENTITY_TYPE,
                comment_id=comment_id,
            ):
                return False
    except Bitrix24Error as exc:
        return _mark_inbound_failure(receipt, exc.code)

    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = datetime.now(UTC)
    receipt.attempts += 1
    return True


async def process_crm_activity_add_event(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    """Import files attached to a CRM activity created in a known client deal."""
    receipt.status = "processing"
    receipt.error_code = None
    await db.flush()
    if receipt.remote_entity_type != CRM_ACTIVITY_ENTITY_TYPE or not receipt.remote_entity_id:
        receipt.status = "ignored"
        receipt.processed_at = datetime.now(UTC)
        return True

    installation = await db.get(BitrixInstallation, receipt.member_id)
    if installation is None:
        return _mark_inbound_failure(receipt, "INSTALLATION_NOT_FOUND")

    activity_id = receipt.remote_entity_id
    try:
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as remote:
            activity = await remote.call("crm.activity.get", {"id": activity_id})
            if not isinstance(activity, dict):
                return _mark_inbound_failure(receipt, "INVALID_ACTIVITY_RESPONSE")
            if FILE_MARKER_PREFIX in str(activity.get("DESCRIPTION") or activity.get("description") or ""):
                receipt.status = "ignored"
                receipt.processed_at = datetime.now(UTC)
                receipt.attempts += 1
                return True
            deal_id = _activity_deal_id(activity)
            if not deal_id:
                receipt.status = "ignored"
                receipt.processed_at = datetime.now(UTC)
                receipt.attempts += 1
                return True
            local_client = await _local_client_for_deal(db, member_id=receipt.member_id, deal_id=deal_id)
            if local_client is None:
                return _mark_inbound_failure(receipt, "CLIENT_DEAL_NOT_FOUND")
            files = _activity_files(activity)
            if not files:
                receipt.status = "ignored"
                receipt.processed_at = datetime.now(UTC)
                receipt.attempts += 1
                return True
            if not await _import_remote_files(
                db,
                remote,
                receipt,
                local_client=local_client,
                parent_id=activity_id,
                files=files,
                remote_entity_type=CRM_ACTIVITY_FILE_REMOTE_ENTITY_TYPE,
                activity_id=activity_id,
            ):
                return False
    except Bitrix24Error as exc:
        return _mark_inbound_failure(receipt, exc.code)

    receipt.status = "completed"
    receipt.error_code = None
    receipt.processed_at = datetime.now(UTC)
    receipt.attempts += 1
    return True


async def process_document_event(db: AsyncSession, receipt: BitrixInboundEvent) -> bool:
    if receipt.remote_entity_type == CRM_ACTIVITY_ENTITY_TYPE:
        return await process_crm_activity_add_event(db, receipt)
    return await process_timeline_comment_add_event(db, receipt)


async def retry_document_events(db: AsyncSession, *, limit: int = 25) -> tuple[int, int]:
    receipts = list(
        (
            await db.scalars(
                select(BitrixInboundEvent)
                .where(
                    or_(
                        BitrixInboundEvent.remote_entity_type == TIMELINE_COMMENT_ENTITY_TYPE,
                        BitrixInboundEvent.remote_entity_type == CRM_ACTIVITY_ENTITY_TYPE,
                    ),
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
        if await process_document_event(db, receipt):
            completed += 1
    await db.commit()
    return len(receipts), completed


retry_timeline_comment_events = retry_document_events
