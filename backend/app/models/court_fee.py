from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.partner import Partner


class CourtFee(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "court_fees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    base_amount: Mapped[int] = mapped_column(Integer, default=0)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="unpaid", index=True)
    due_date: Mapped[date] = mapped_column(index=True)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    client: Mapped[Client] = relationship("Client")
    partner: Mapped[Partner] = relationship("Partner")

    def __repr__(self) -> str:
        return f"<CourtFee {self.amount} status={self.status}>"
