from typing import Literal

from sqlalchemy import String, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.models.task import Task
from app.schemas.bitrix_attention import BitrixAttentionItem, BitrixAttentionResponse

EntityType = Literal["all", "partner", "client", "file", "task"]
SyncStatus = Literal["all", "failed", "conflict", "pending", "not_scheduled"]


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
    ).where(_attention_condition(model))


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
        items=[BitrixAttentionItem(**dict(row)) for row in rows],
        total=total,
        page=page,
        pages=(total + page_size - 1) // page_size if total else 0,
        page_size=page_size,
        counts=counts,
    )
