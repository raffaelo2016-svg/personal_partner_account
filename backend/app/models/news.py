from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime


class NewsPost(Base, TimestampMixin):
    __tablename__ = "news_posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), default="announcement")
    important: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_acknowledgement: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class NewsReceipt(Base):
    __tablename__ = "news_receipts"

    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_posts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
