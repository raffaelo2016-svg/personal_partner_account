from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.pagination import PaginatedResponse


class ChatDocumentCandidate(BaseModel):
    client_id: str
    full_name: str
    status: str
    score: int
    matched_on: Literal["filename", "text"]


class ChatDocumentAttachment(BaseModel):
    url: str
    filename: str
    size: int | None = None
    mime_type: str | None = None


class ChatDocumentAssignmentRead(BaseModel):
    message_id: str
    status: Literal["assigned", "ignored"]
    client_id: str | None = None
    client_name: str | None = None
    document_type: str | None = None
    file_id: str | None = None
    assigned_at: datetime | None = None
    document_name: str | None = None
    duplicate: bool = False
    bitrix_sync_status: str | None = None
    bitrix_sync_error_code: str | None = None


class ChatDocumentInboxItem(BaseModel):
    message_id: str
    room_id: str
    partner_id: str
    partner_name: str | None = None
    sender_type: str
    sender_label: str
    text: str
    created_at: datetime
    attachment: ChatDocumentAttachment
    status: Literal["unassigned", "assigned", "ignored"]
    candidates: list[ChatDocumentCandidate] = Field(default_factory=list)
    assignment: ChatDocumentAssignmentRead | None = None


class ChatDocumentInboxResponse(PaginatedResponse[ChatDocumentInboxItem]):
    pass


class ChatDocumentAssignRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    document_type: str = Field(min_length=1, max_length=100)
    # Admin-editable document name; extension must match the chat attachment.
    filename: str | None = Field(default=None, max_length=300)
    sync_to_bitrix: bool = True


class ChatDocumentInboxCount(BaseModel):
    unassigned: int
