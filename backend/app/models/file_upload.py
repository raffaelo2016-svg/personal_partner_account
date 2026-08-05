from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client


class FileUpload(Base, TimestampMixin):
    __tablename__ = "file_uploads"
    __table_args__ = (
        CheckConstraint(
            "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
            name="ck_file_uploads_bitrix_sync_status",
        ),
        Index("ix_file_uploads_bitrix_sync_status", "bitrix_sync_status"),
        Index(
            "uq_file_uploads_client_content_sha256",
            "client_id",
            "content_sha256",
            unique=True,
            postgresql_where=text("content_sha256 IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(100))
    original_name: Mapped[str] = mapped_column(String(500))
    s3_key: Mapped[str] = mapped_column(String(500), unique=True)
    size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100))
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bitrix_sync_status: Mapped[str] = mapped_column(String(20), default="not_scheduled", server_default="not_scheduled")
    bitrix_sync_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bitrix_timeline_comment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bitrix_activity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bitrix_disk_file_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bitrix_sync_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[Client] = relationship("Client")

    def __repr__(self) -> str:
        return f"<FileUpload {self.original_name} ({self.mime_type})>"
