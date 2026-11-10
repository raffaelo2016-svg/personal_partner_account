from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.partner import Partner


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    login: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, default=None)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_legacy_shared: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    password_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    partner: Mapped[Partner | None] = relationship("Partner", back_populates="user", uselist=False)

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "super_admin")

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"
