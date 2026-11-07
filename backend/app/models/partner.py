from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.client import Client
    from app.models.user import User


class Partner(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "partners"
    __table_args__ = (
        CheckConstraint(
            "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed', 'conflict')",
            name="ck_partners_bitrix_sync_status",
        ),
        CheckConstraint(
            "bitrix_collab_status IN ('not_linked', 'binding_required', 'linked')",
            name="ck_partners_bitrix_collab_status",
        ),
        Index("ix_partners_bitrix_sync_status", "bitrix_sync_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)

    partner_type: Mapped[str] = mapped_column(String(20), default="individual")
    company_name: Mapped[str] = mapped_column(String(255))
    director_name: Mapped[str] = mapped_column(String(255))
    inn: Mapped[str] = mapped_column(String(12))
    phone: Mapped[str] = mapped_column(String(30))

    short_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_legal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    legal_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    postal_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)

    court_fee_per_client: Mapped[int] = mapped_column(default=1_500_000)
    payment_term_days: Mapped[int] = mapped_column(default=10)
    free_client_limit: Mapped[int] = mapped_column(default=0)
    promotion_start_date: Mapped[date | None] = mapped_column(default=None)
    promotion_end_date: Mapped[date | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Агентская программа: партнёр закрепляется за агентом один раз.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), default=None, index=True
    )
    agent_linked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    # Bitrix24 is an operational projection. Cabinet requisites remain authoritative.
    bitrix_sync_status: Mapped[str] = mapped_column(String(20), default="not_scheduled")
    bitrix_sync_error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_partner_item_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_collab_status: Mapped[str] = mapped_column(String(20), default="not_linked")
    bitrix_collab_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_chat_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_chat_bot_joined_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    bitrix_root_folder_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_sync_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    user: Mapped[User] = relationship("User", back_populates="partner")
    clients: Mapped[list[Client]] = relationship("Client", back_populates="partner")

    agent: Mapped[Agent | None] = relationship("Agent", back_populates="partners")

    def __repr__(self) -> str:
        return f"<Partner {self.company_name}>"
