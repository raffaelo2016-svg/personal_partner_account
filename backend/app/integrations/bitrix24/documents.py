from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.partners import active_installation
from app.models.bitrix_sync import BitrixEntityMap, BitrixOutboxOperation
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.services.s3_service import download_file_async

FILE_ENTITY_TYPE = "file"
FILE_CREATE_METHOD = "crm.timeline.comment.add"
FILE_MARKER_PREFIX = "partner-cabinet-file:"


def file_marker(file_id: uuid.UUID) -> str:
    return f"[{FILE_MARKER_PREFIX}{file_id}]"


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
    files = comment.get("FILES") or comment.get("files") or []
    if not comment_id or not isinstance(files, list) or not files:
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
