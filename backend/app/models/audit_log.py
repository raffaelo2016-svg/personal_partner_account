from __future__ import annotations

import uuid

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    actor_label: Mapped[str | None] = mapped_column(String(255), default=None)
    target_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), default=None)
    target_label: Mapped[str | None] = mapped_column(String(255), default=None)
    result: Mapped[str] = mapped_column(String(16), default="success")
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} user={self.user_id}>"
