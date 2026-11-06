from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.user import User


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SystemSetting {self.key}>"


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True,
    )
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    new_partner_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    critical_events: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, default=None)
    telegram_username: Mapped[str | None] = mapped_column(String(64), default=None)
    telegram_connected_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    telegram_connect_token_hash: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    telegram_connect_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<NotificationPreference user={self.user_id}>"


class LoginHistory(Base):
    __tablename__ = "login_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(500), default=None)
    logged_at: Mapped[datetime] = mapped_column(UTCDateTime, default=func.now())

    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<LoginHistory user={self.user_id}>"
