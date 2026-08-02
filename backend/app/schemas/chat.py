import html
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChatRoomRead(BaseModel):
    id: str
    partner_id: str
    type: str
    created_at: datetime
    last_message: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0
    partner_name: str | None = None

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def _escape_html(cls, v: str) -> str:
        # Escape HTML to prevent stored XSS; frontend should still escape on render.
        return html.escape(v.strip(), quote=True)


class ChatMessageRead(BaseModel):
    id: str
    room_id: str
    sender_id: str | None = None
    sender_type: str
    text: str
    delivery_status: str  # sent, delivered, read
    bitrix_sync_status: str
    bitrix_sync_error_code: str | None = None
    bitrix_message_id: str | None = None
    attachment_url: str | None = None
    attachment_filename: str | None = None
    attachment_size: int | None = None
    attachment_mime_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageEventRead(BaseModel):
    id: str
    room_id: str
    chat_message_id: str | None = None
    bitrix_message_id: str
    event_type: str
    actor_id: str | None = None
    event_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
