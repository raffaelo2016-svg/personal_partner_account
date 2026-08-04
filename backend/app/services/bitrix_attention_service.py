import re
import uuid
from typing import Literal

from sqlalchemy import String, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixInboundEvent
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.models.task import Task
from app.schemas.bitrix_attention import BitrixAttentionItem, BitrixAttentionResponse
from app.services.audit import audit_log

EntityType = Literal["all", "partner", "client", "file", "task", "inbound_client", "inbound_file"]
SyncStatus = Literal["all", "failed", "conflict", "pending", "not_scheduled"]

INBOUND_CLIENT_ENTITY_TYPE = "client_deal"
INBOUND_FILE_ENTITY_TYPE = "timeline_comment"
_SAFE_PORTAL_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,253}[a-z0-9])?$")


def _attention_condition(model):
    return or_(
        model.bitrix_sync_error_code.is_not(None),
        model.bitrix_sync_status.in_(("failed", "conflict")),
    )


def _projection_query(entity_type: str, model, *, parent_column=None):
    parent = cast(parent_column, String) if parent_column is not None else cast(literal(None), String)
    return select(
        literal(entity_type).label("entity_type"),
        cast(model.id, String).label("entity_id"),
        parent.label("parent_id"),
        model.bitrix_sync_status.label("sync_status"),
        func.coalesce(model.bitrix_sync_error_code, "UNKNOWN_ERROR").label("error_code"),
        func.coalesce(model.bitrix_sync_requested_at, model.updated_at, model.created_at).label("occurred_at"),
        cast(literal(None), String).label("remote_id"),
        cast(literal(None), String).label("portal_domain"),
    ).where(_attention_condition(model))


def _inbound_client_query():
    return (
        select(
            literal("inbound_client").label("entity_type"),
            cast(BitrixInboundEvent.id, String).label("entity_id"),
            cast(literal(None), String).label("parent_id"),
            literal("conflict").label("sync_status"),
            func.coalesce(BitrixInboundEvent.error_code, "UNKNOWN_ERROR").label("error_code"),
            func.coalesce(
                BitrixInboundEvent.processed_at,
                BitrixInboundEvent.updated_at,
                BitrixInboundEvent.created_at,
            ).label("occurred_at"),
            BitrixInboundEvent.remote_entity_id.label("remote_id"),
            BitrixInstallation.portal_domain.label("portal_domain"),
        )
        .join(BitrixInstallation, BitrixInstallation.member_id == BitrixInboundEvent.member_id)
        .where(
            BitrixInboundEvent.remote_entity_type == INBOUND_CLIENT_ENTITY_TYPE,
            BitrixInboundEvent.status == "failed",
        )
    )


def _inbound_file_query():
    return (
        select(
            literal("inbound_file").label("entity_type"),
            cast(BitrixInboundEvent.id, String).label("entity_id"),
            cast(literal(None), String).label("parent_id"),
            literal("conflict").label("sync_status"),
            func.coalesce(BitrixInboundEvent.error_code, "UNKNOWN_ERROR").label("error_code"),
            func.coalesce(
                BitrixInboundEvent.processed_at,
                BitrixInboundEvent.updated_at,
                BitrixInboundEvent.created_at,
            ).label("occurred_at"),
            BitrixInboundEvent.remote_entity_id.label("remote_id"),
            BitrixInstallation.portal_domain.label("portal_domain"),
        )
        .join(BitrixInstallation, BitrixInstallation.member_id == BitrixInboundEvent.member_id)
        .where(
            BitrixInboundEvent.remote_entity_type == INBOUND_FILE_ENTITY_TYPE,
            BitrixInboundEvent.status == "failed",
        )
    )


def _deal_url(portal_domain: str | None, remote_id: str | None) -> str | None:
    domain = str(portal_domain or "").strip().lower()
    deal_id = str(remote_id or "").strip()
    if not domain or "." not in domain or not _SAFE_PORTAL_DOMAIN.fullmatch(domain) or not deal_id.isdigit():
        return None
    return f"https://{domain}/crm/deal/details/{deal_id}/"


async def list_bitrix_attention(
    db: AsyncSession,
    *,
    entity_type: EntityType = "all",
    sync_status: SyncStatus = "all",
    page: int = 1,
    page_size: int = 20,
) -> BitrixAttentionResponse:
    queries = {
        "partner": _projection_query("partner", Partner).where(Partner.deleted_at.is_(None)),
        "client": _projection_query("client", Client, parent_column=Client.partner_id).where(
            Client.deleted_at.is_(None)
        ),
        "file": _projection_query("file", FileUpload, parent_column=FileUpload.client_id).where(
            FileUpload.client.has(Client.deleted_at.is_(None))
        ),
        "task": _projection_query("task", Task, parent_column=Task.client_id).where(
            Task.client.has(Client.deleted_at.is_(None))
        ),
        "inbound_client": _inbound_client_query(),
        "inbound_file": _inbound_file_query(),
    }
    selected = list(queries.values()) if entity_type == "all" else [queries[entity_type]]
    attention = union_all(*selected).subquery("bitrix_attention")

    filters = []
    if sync_status != "all":
        filters.append(attention.c.sync_status == sync_status)

    total = int(await db.scalar(select(func.count()).select_from(attention).where(*filters)) or 0)
    rows = (
        (
            await db.execute(
                select(attention)
                .where(*filters)
                .order_by(attention.c.occurred_at.desc(), attention.c.entity_type, attention.c.entity_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )

    all_attention = union_all(*queries.values()).subquery("all_bitrix_attention")
    count_rows = (
        await db.execute(
            select(all_attention.c.entity_type, func.count().label("count")).group_by(all_attention.c.entity_type)
        )
    ).all()
    counts = {kind: 0 for kind in queries}
    counts.update({str(row.entity_type): int(row.count) for row in count_rows})

    return BitrixAttentionResponse(
        items=[
            BitrixAttentionItem(
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                parent_id=row["parent_id"],
                sync_status=row["sync_status"],
                error_code=row["error_code"],
                occurred_at=row["occurred_at"],
                remote_id=row["remote_id"],
                external_url=(
                    _deal_url(row["portal_domain"], row["remote_id"])
                    if row["entity_type"] == "inbound_client"
                    else None
                ),
            )
            for row in rows
        ],
        total=total,
        page=page,
        pages=(total + page_size - 1) // page_size if total else 0,
        page_size=page_size,
        counts=counts,
    )


async def retry_inbound_client_event(db: AsyncSession, receipt_id: uuid.UUID) -> None:
    receipt = await db.get(BitrixInboundEvent, receipt_id)
    if receipt is None or receipt.remote_entity_type != INBOUND_CLIENT_ENTITY_TYPE:
        raise NotFound("Inbound client receipt not found")
    if receipt.status != "failed":
        raise BadRequest("Inbound client receipt is not waiting for manual review")

    receipt.status = "received"
    receipt.attempts = 0
    receipt.error_code = None
    receipt.processed_at = None
    audit_log(
        action="retry_client_import_from_bitrix",
        target_id=str(receipt.id),
        target_type="bitrix_inbound_event",
    )
    await db.flush()


async def retry_inbound_file_event(db: AsyncSession, receipt_id: uuid.UUID) -> None:
    receipt = await db.get(BitrixInboundEvent, receipt_id)
    if receipt is None or receipt.remote_entity_type != INBOUND_FILE_ENTITY_TYPE:
        raise NotFound("Inbound file receipt not found")
    if receipt.status != "failed":
        raise BadRequest("Inbound file receipt is not waiting for manual review")

    receipt.status = "received"
    receipt.attempts = 0
    receipt.error_code = None
    receipt.processed_at = None
    audit_log(
        action="retry_file_import_from_bitrix",
        target_id=str(receipt.id),
        target_type="bitrix_inbound_event",
    )
    await db.flush()
