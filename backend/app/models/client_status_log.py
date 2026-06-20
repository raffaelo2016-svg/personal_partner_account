from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.user import User


class ClientStatusLog(Base):
    __tablename__ = "client_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50))
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(default=None)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=func.now())

    client: Mapped[Client] = relationship("Client")
    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<StatusLog {self.from_status} -> {self.to_status}>"
