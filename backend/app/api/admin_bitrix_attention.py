import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.schemas.bitrix_attention import BitrixAttentionResponse
from app.schemas.pagination import PaginationParams
from app.services.bitrix_attention_service import list_bitrix_attention, retry_inbound_client_event

router = APIRouter(prefix="/admin/bitrix-attention", tags=["admin-bitrix-attention"])


@router.get("", response_model=BitrixAttentionResponse)
async def get_bitrix_attention(
    entity_type: Literal["all", "partner", "client", "file", "task", "inbound_client"] = Query("all"),  # noqa: B008
    sync_status: Literal["all", "failed", "conflict", "pending", "not_scheduled"] = Query("all"),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    return await list_bitrix_attention(
        db,
        entity_type=entity_type,
        sync_status=sync_status,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/inbound-clients/{receipt_id}/retry", status_code=status.HTTP_204_NO_CONTENT)
async def retry_inbound_client(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    await retry_inbound_client_event(db, receipt_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
