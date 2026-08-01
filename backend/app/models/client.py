from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.partner import Partner


class Client(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"
    __table_args__ = (
        CheckConstraint(
            "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
            name="ck_clients_bitrix_sync_status",
        ),
        Index("ix_clients_bitrix_sync_status", "bitrix_sync_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(50), default="documents_collection", index=True)

    full_name: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date | None] = mapped_column(default=None)
    passport_series: Mapped[str | None] = mapped_column(String(4), default=None)
    passport_number: Mapped[str | None] = mapped_column(String(6), default=None)
    passport_issue_date: Mapped[date | None] = mapped_column(default=None)
    passport_issued_by: Mapped[str | None] = mapped_column(String(500), default=None)
    registration_address: Mapped[str | None] = mapped_column(String(500), default=None)
    inn: Mapped[str | None] = mapped_column(String(12), default=None)
    snils: Mapped[str | None] = mapped_column(String(14), default=None)

    phone: Mapped[str | None] = mapped_column(String(20), default=None, index=True)
    email: Mapped[str | None] = mapped_column(String(255), default=None, index=True)

    region: Mapped[str | None] = mapped_column(String(100), default=None)
    arbitrage_court: Mapped[str | None] = mapped_column(String(255), default=None)
    case_number: Mapped[str | None] = mapped_column(String(50), default=None)
    court_procedure_date: Mapped[date | None] = mapped_column(default=None, index=True)

    # Bitrix24 is an operational projection. Sensitive identity data stays here.
    bitrix_sync_status: Mapped[str] = mapped_column(String(20), default="not_scheduled")
    bitrix_sync_error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_contact_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_deal_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_sync_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    partner: Mapped[Partner] = relationship("Partner", back_populates="clients")

    def __repr__(self) -> str:
        return f"<Client {self.full_name} status={self.status}>"
