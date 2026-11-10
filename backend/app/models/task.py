from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.partner import Partner
    from app.models.user import User


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
            name="ck_tasks_bitrix_sync_status",
        ),
        Index("ix_tasks_bitrix_sync_status", "bitrix_sync_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id"), index=True, default=None)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), index=True, default=None)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    assigned_to: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(index=True, default=None)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    bitrix_sync_status: Mapped[str] = mapped_column(String(20), default="not_scheduled")
    bitrix_sync_error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_task_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_imported: Mapped[bool] = mapped_column(default=False)
    bitrix_published: Mapped[bool] = mapped_column(default=True)
    bitrix_sync_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    partner: Mapped[Partner | None] = relationship("Partner")
    client: Mapped[Client | None] = relationship("Client")
    creator: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<Task {self.title} status={self.status}>"
