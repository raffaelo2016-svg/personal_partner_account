from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.user import User


class Partner(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "partners"

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
    status: Mapped[str] = mapped_column(String(20), default="pending")

    user: Mapped[User] = relationship("User", back_populates="partner")
    clients: Mapped[list[Client]] = relationship("Client", back_populates="partner")

    def __repr__(self) -> str:
        return f"<Partner {self.company_name}>"
