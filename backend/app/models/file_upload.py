from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client


class FileUpload(Base, TimestampMixin):
    __tablename__ = "file_uploads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(100))
    original_name: Mapped[str] = mapped_column(String(500))
    s3_key: Mapped[str] = mapped_column(String(500), unique=True)
    size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100))

    client: Mapped[Client] = relationship("Client")

    def __repr__(self) -> str:
        return f"<FileUpload {self.original_name} ({self.mime_type})>"
