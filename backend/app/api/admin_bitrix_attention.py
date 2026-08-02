from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.schemas.bitrix_attention import BitrixAttentionResponse
from app.schemas.pagination import PaginationParams
from app.services.bitrix_attention_service import list_bitrix_attention

router = APIRouter(prefix="/admin/bitrix-attention", tags=["admin-bitrix-attention"])


@router.get("", response_model=BitrixAttentionResponse)
async def get_bitrix_attention(
    entity_type: Literal["all", "partner", "client", "file", "task"] = Query("all"),  # noqa: B008
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
