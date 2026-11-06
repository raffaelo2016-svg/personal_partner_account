"""Assignment of a chat attachment to a client document."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.chat import ChatMessage
    from app.models.client import Client
    from app.models.file_upload import FileUpload


class ChatAttachmentAssignment(Base, TimestampMixin):
    """One chat attachment routed to a client document (or dismissed).

    A message carries at most one attachment, so one row per message is enough.
    ``status='assigned'`` rows keep the created document link; ``ignored`` rows
    keep only who dismissed the file and when.
    """

    __tablename__ = "chat_attachment_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('assigned', 'ignored')",
            name="ck_chat_attachment_assignments_status",
        ),
        Index(
            "uq_chat_attachment_assignments_message",
            "chat_message_id",
            unique=True,
        ),
        Index("ix_chat_attachment_assignments_status", "status"),
        Index("ix_chat_attachment_assignments_client_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chat_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_uploads.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    message: Mapped[ChatMessage] = relationship("ChatMessage")
    client: Mapped[Client | None] = relationship("Client")
    file: Mapped[FileUpload | None] = relationship("FileUpload")
