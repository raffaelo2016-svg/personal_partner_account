from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.court_fee import CourtFee
    from app.models.partner import Partner


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    court_fee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("court_fees.id"), default=None)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    payment_method: Mapped[str | None] = mapped_column(String(50), default=None)
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)

    partner: Mapped[Partner] = relationship("Partner")
    court_fee: Mapped[CourtFee | None] = relationship("CourtFee")

    def __repr__(self) -> str:
        return f"<Transaction {self.amount} status={self.status}>"
