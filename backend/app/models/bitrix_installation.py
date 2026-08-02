from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime


class BitrixInstallation(Base, TimestampMixin):
    __tablename__ = "bitrix_installations"

    member_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portal_domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    client_endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    server_endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    application_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    scope: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="L")
    installed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    im_event_offset: Mapped[int | None] = mapped_column(BigInteger, default=None)
    im_event_subscribed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
