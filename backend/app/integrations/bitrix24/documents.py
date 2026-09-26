from __future__ import annotations

import base64
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse

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
from app.models.partner import Partner
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
DISK_FILE_MARKER_PREFIX = "partner-cabinet-disk-file:"
PARTNERS_FOLDER_NAME = "ПАРТНЕРЫ"
INITIAL_DOCUMENTS_FOLDER_NAME = "Первоначальные документы"
SAMSONYUK_TEST_PARTNER_NAME = "Самсонюк Евгений Вячеславович"
TIMELINE_COMMENT_ADD_EVENT = "ONCRMTIMELINECOMMENTADD"
TIMELINE_COMMENT_ENTITY_TYPE = "timeline_comment"
TIMELINE_FILE_REMOTE_ENTITY_TYPE = "crm_timeline_file"
TIMELINE_EVENT_HANDLER = "https://finzdorovie.ru/api/v1/integrations/bitrix24/handler"
CRM_ACTIVITY_ADD_EVENT = "ONCRMACTIVITYADD"
CRM_ACTIVITY_ENTITY_TYPE = "crm_activity"
CRM_ACTIVITY_FILE_REMOTE_ENTITY_TYPE = "crm_activity_file"


@dataclass(frozen=True)
class FileFolderContext:
    partner_root_folder_id: str | None
    partner_folder_name: str
    client_folder_name: str
    remote_file_name: str


def file_marker(file_id: uuid.UUID) -> str:
    return f"[{FILE_MARKER_PREFIX}{file_id}]"


def disk_file_marker(file_id: str) -> str:
    return f"[{DISK_FILE_MARKER_PREFIX}{file_id}]"


def client_folder_name(client: Client) -> str:
    """Build the exact readable client folder name without persisting PII in the outbox."""
    cleaned_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", client.full_name).strip(" .")
    cleaned_name = re.sub(r"\s+", " ", cleaned_name) or "Клиент"
    return cleaned_name[:200]


def disk_file_name(record: FileUpload) -> str:
    """Keep the original name recognizable and add a stable suffix for safe retries."""
    source_name = PurePosixPath(record.original_name.replace("\\", "/")).name
    extension = PurePosixPath(record.s3_key).suffix.lower() or PurePosixPath(source_name).suffix.lower()
    stem = source_name[: -len(extension)] if extension and source_name.lower().endswith(extension) else source_name
    cleaned_stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", stem).strip(" .") or "document"
    suffix = f" [{record.id.hex[:8]}]{extension}"
    return f"{cleaned_stem[: max(1, 240 - len(suffix))]}{suffix}"


def partner_uses_disk_pilot(partner: Partner) -> bool:
    target = " ".join(SAMSONYUK_TEST_PARTNER_NAME.casefold().split())
    candidates = (partner.company_name, partner.director_name, partner.short_name, partner.full_legal_name)
    return any(" ".join((value or "").casefold().split()) == target for value in candidates)


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


async def load_file_folder_context(
    db: AsyncSession,
    operation: BitrixOutboxOperation,
) -> FileFolderContext | None:
    record = await db.get(FileUpload, operation.local_entity_id)
    if record is None:
        raise Bitrix24Error("LOCAL_FILE_UNAVAILABLE", "Document record was not found")
    local_client = await db.get(Client, record.client_id)
    if local_client is None:
        raise Bitrix24Error("LOCAL_CLIENT_UNAVAILABLE", "Document client was not found")
    partner = await db.get(Partner, local_client.partner_id)
    if partner is None:
        raise Bitrix24Error("LOCAL_PARTNER_UNAVAILABLE", "Document partner was not found")
    if not partner_uses_disk_pilot(partner):
        return None
    return FileFolderContext(
        partner_root_folder_id=partner.bitrix_root_folder_id,
        partner_folder_name=SAMSONYUK_TEST_PARTNER_NAME,
        client_folder_name=client_folder_name(local_client),
        remote_file_name=disk_file_name(record),
    )


def _comment_reference(comment: dict[str, Any]) -> str | None:
    comment_id = comment.get("ID") or comment.get("id")
    comment_text = str(comment.get("COMMENT") or comment.get("comment") or "")
    disk_marker = re.search(rf"\[{re.escape(DISK_FILE_MARKER_PREFIX)}([^\]]+)\]", comment_text)
    if comment_id and disk_marker:
        return f"{comment_id}:{disk_marker.group(1)}"
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


def _object_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    candidate = value.get("ID") or value.get("id")
    return str(candidate).strip() if candidate is not None and str(candidate).strip() else None


async def _find_folder_child(client: Bitrix24Client, parent_id: str, name: str) -> dict[str, Any] | None:
    children = await client.list_all(
        "disk.folder.getchildren",
        {"id": parent_id, "filter": {"NAME": name}},
        max_pages=20,
    )
    for child in children:
        if not isinstance(child, dict):
            continue
        if str(child.get("TYPE") or child.get("type") or "").lower() != "folder":
            continue
        if str(child.get("NAME") or child.get("name") or "") == name and _object_id(child):
            return child
    return None


async def _ensure_subfolder(client: Bitrix24Client, parent_id: str, name: str) -> dict[str, Any]:
    existing = await _find_folder_child(client, parent_id, name)
    if existing is not None:
        return existing
    try:
        created = await client.call("disk.folder.addsubfolder", {"id": parent_id, "data": {"NAME": name}})
    except Bitrix24Error:
        # A parallel worker may have created the same deterministic folder.
        existing = await _find_folder_child(client, parent_id, name)
        if existing is not None:
            return existing
        raise
    if not isinstance(created, dict) or not _object_id(created):
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return the created folder")
    return created


async def _find_disk_file(client: Bitrix24Client, folder_id: str, name: str) -> dict[str, Any] | None:
    children = await client.list_all(
        "disk.folder.getchildren",
        {"id": folder_id, "filter": {"NAME": name}},
        max_pages=20,
    )
    for child in children:
        if not isinstance(child, dict):
            continue
        if str(child.get("TYPE") or child.get("type") or "").lower() != "file":
            continue
        if str(child.get("NAME") or child.get("name") or "") == name and _object_id(child):
            return child
    return None


async def _find_partners_folder(client: Bitrix24Client) -> dict[str, Any]:
    # The portal may expose hundreds of personal drives. The shared ``ПАРТНЕРЫ``
    # directory can only live in the company (common) storage, so do not page
    # through every user storage.
    storages = await client.list_all(
        "disk.storage.getlist",
        {"filter": {"ENTITY_TYPE": "common"}},
        max_pages=5,
    )
    for storage in storages:
        storage_id = _object_id(storage)
        if not storage_id:
            continue
        children = await client.list_all(
            "disk.storage.getchildren",
            {"id": storage_id, "filter": {"NAME": PARTNERS_FOLDER_NAME}},
            max_pages=20,
        )
        for child in children:
            if not isinstance(child, dict):
                continue
            if str(child.get("TYPE") or child.get("type") or "").lower() != "folder":
                continue
            if str(child.get("NAME") or child.get("name") or "") == PARTNERS_FOLDER_NAME and _object_id(child):
                return child
    raise Bitrix24Error("PARTNERS_FOLDER_NOT_FOUND", "Shared Drive folder ПАРТНЕРЫ was not found")


def _absolute_detail_url(client: Bitrix24Client, item: dict[str, Any]) -> str | None:
    detail_url = str(item.get("DETAIL_URL") or item.get("detailUrl") or "").strip()
    if not detail_url:
        return None
    parsed = urlparse(detail_url)
    if parsed.scheme and parsed.netloc:
        portal_host = (urlparse(client.client_endpoint).hostname or "").lower()
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != portal_host:
            return None
        return detail_url
    absolute = urljoin(client.client_endpoint, f"/{detail_url.lstrip('/')}")
    return absolute if urlparse(absolute).scheme == "https" else None


async def _upload_to_initial_documents(
    client: Bitrix24Client,
    *,
    context: FileFolderContext,
    remote_name: str,
    data: bytes,
) -> dict[str, Any]:
    partner_folder_id = context.partner_root_folder_id
    if not partner_folder_id:
        partners_folder = await _find_partners_folder(client)
        partners_folder_id = _object_id(partners_folder)
        if not partners_folder_id:
            raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 partners folder has no ID")
        partner_folder = await _ensure_subfolder(client, partners_folder_id, context.partner_folder_name)
        partner_folder_id = _object_id(partner_folder)
        if not partner_folder_id:
            raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 partner folder has no ID")

    client_folder = await _ensure_subfolder(client, partner_folder_id, context.client_folder_name)
    client_folder_id = _object_id(client_folder)
    if not client_folder_id:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 client folder has no ID")
    documents_folder = await _ensure_subfolder(client, client_folder_id, INITIAL_DOCUMENTS_FOLDER_NAME)
    documents_folder_id = _object_id(documents_folder)
    if not documents_folder_id:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 documents folder has no ID")

    existing = await _find_disk_file(client, documents_folder_id, remote_name)
    if existing is not None:
        return existing
    uploaded = await client.call(
        "disk.folder.uploadfile",
        {
            "id": documents_folder_id,
            "data": {"NAME": remote_name},
            "fileContent": [remote_name, base64.b64encode(data).decode("ascii")],
            "generateUniqueName": False,
        },
    )
    if not isinstance(uploaded, dict) or not _object_id(uploaded):
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return the uploaded document")
    return uploaded


async def execute_file_creation(
    client: Bitrix24Client,
    operation: BitrixOutboxOperation,
    *,
    folder_context: FileFolderContext | None,
) -> str:
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

    if folder_context is None:
        result = await client.call(
            FILE_CREATE_METHOD,
            {
                "fields": {
                    "ENTITY_ID": deal_id,
                    "ENTITY_TYPE": "deal",
                    "COMMENT": f"Документ из партнёрского кабинета\n{marker}",
                    "FILES": [
                        [
                            str(payload.get("remote_name") or "document"),
                            base64.b64encode(data).decode("ascii"),
                        ]
                    ],
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

    remote_name = folder_context.remote_file_name
    disk_file = await _upload_to_initial_documents(
        client,
        context=folder_context,
        remote_name=remote_name,
        data=data,
    )
    disk_file_id = _object_id(disk_file)
    if not disk_file_id:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return an uploaded Disk file ID")
    detail_url = _absolute_detail_url(client, disk_file)
    if detail_url is None:
        refreshed = await client.call("disk.file.get", {"id": disk_file_id})
        if isinstance(refreshed, dict):
            detail_url = _absolute_detail_url(client, refreshed)
    if detail_url is None:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return a document link")

    result = await client.call(
        FILE_CREATE_METHOD,
        {
            "fields": {
                "ENTITY_ID": deal_id,
                "ENTITY_TYPE": "deal",
                "COMMENT": (
                    "Документ из партнёрского кабинета\n"
                    f"Папка: {folder_context.client_folder_name} / {INITIAL_DOCUMENTS_FOLDER_NAME}\n"
                    f"Файл: {detail_url}\n{marker}\n{disk_file_marker(disk_file_id)}"
                ),
            }
        },
    )
    comment_id = result if isinstance(result, str | int) else None
    if not comment_id:
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return a timeline comment ID")
    return f"{comment_id}:{disk_file_id}"


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
