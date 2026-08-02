from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.partner import Partner
    from app.models.user import User


class ChatRoom(Base, TimestampMixin):
    __tablename__ = "chat_rooms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))

    partner: Mapped[Partner] = relationship("Partner")

    def __repr__(self) -> str:
        return f"<ChatRoom {self.type} partner={self.partner_id}>"


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
            name="ck_chat_messages_bitrix_sync_status",
        ),
        Index("ix_chat_messages_bitrix_sync_status", "bitrix_sync_status"),
        Index(
            "uq_chat_messages_bitrix_message_id",
            "bitrix_message_id",
            unique=True,
            postgresql_where=text("bitrix_message_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_rooms.id"), index=True)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(String(10), default="sent")  # sent, delivered, read
    attachment_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_size: Mapped[int | None] = mapped_column(nullable=True)
    attachment_mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="cabinet")
    bitrix_sync_status: Mapped[str] = mapped_column(String(20), default="not_scheduled")
    bitrix_sync_error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_message_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_author_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_sync_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    room: Mapped[ChatRoom] = relationship("ChatRoom")
    sender: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.sender_type} in room={self.room_id}>"


class ChatMessageEvent(Base, TimestampMixin):
    __tablename__ = "chat_message_events"
    __table_args__ = (
        UniqueConstraint("member_id", "bitrix_event_id", name="uq_chat_message_events_remote"),
        Index("ix_chat_message_events_room_date", "room_id", "event_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("bitrix_installations.member_id", ondelete="CASCADE"),
        index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_rooms.id", ondelete="CASCADE"), index=True)
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    bitrix_event_id: Mapped[int] = mapped_column(BigInteger)
    bitrix_message_id: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str | None] = mapped_column(String(100), default=None)
    event_at: Mapped[datetime] = mapped_column(UTCDateTime)
