from datetime import datetime
from typing import Literal

from pydantic import BaseModel

BitrixAttentionEntityType = Literal["partner", "client", "file", "task"]


class BitrixAttentionItem(BaseModel):
    entity_type: BitrixAttentionEntityType
    entity_id: str
    parent_id: str | None = None
    sync_status: str
    error_code: str
    occurred_at: datetime


class BitrixAttentionResponse(BaseModel):
    items: list[BitrixAttentionItem]
    total: int
    page: int
    pages: int
    page_size: int
    counts: dict[str, int]
