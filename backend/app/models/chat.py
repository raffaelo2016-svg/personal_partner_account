from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

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

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_rooms.id"), index=True)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(String(10), default="sent")  # sent, delivered, read

    room: Mapped[ChatRoom] = relationship("ChatRoom")
    sender: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.sender_type} in room={self.room_id}>"
