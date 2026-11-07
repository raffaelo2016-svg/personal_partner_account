from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.partner import Partner
    from app.models.user import User


class Agent(Base, TimestampMixin):
    """Агент: приводит юристов и компании, получает вознаграждение за их клиентов."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(30), default="")
    company_name: Mapped[str | None] = mapped_column(String(255), default=None)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)

    requisites_recipient_type: Mapped[str] = mapped_column(String(20), default="individual")
    requisites: Mapped[dict] = mapped_column(JSON, default=dict)
    requisites_status: Mapped[str] = mapped_column(String(20), default="empty")

    user: Mapped[User] = relationship("User", lazy="joined")
    partners: Mapped[list[Partner]] = relationship("Partner", back_populates="agent")

    def __repr__(self) -> str:
        return f"<Agent {self.full_name} code={self.code}>"


class AgentAccrual(Base, TimestampMixin):
    """Начисление агенту. Одно дело — одно начисление."""

    __tablename__ = "agent_accruals"
    __table_args__ = (
        UniqueConstraint("client_id", name="uq_agent_accruals_client"),
        Index("ix_agent_accruals_agent_status", "agent_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)

    amount: Mapped[int] = mapped_column(default=0)
    rate: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="accrued", index=True)
    reason: Mapped[str] = mapped_column(String(100), default="procedure_started")
    comment: Mapped[str | None] = mapped_column(String(500), default=None)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)

    client: Mapped[Client] = relationship("Client", lazy="joined")
    partner: Mapped[Partner] = relationship("Partner", lazy="joined")

    def __repr__(self) -> str:
        return f"<AgentAccrual {self.amount} status={self.status}>"


class AgentPayoutRequest(Base, TimestampMixin):
    """Заявка агента на выплату. Одна заявка на всю доступную сумму."""

    __tablename__ = "agent_payout_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    amount: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    period: Mapped[str] = mapped_column(String(7), default="")
    comment: Mapped[str | None] = mapped_column(String(500), default=None)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    def __repr__(self) -> str:
        return f"<AgentPayoutRequest {self.amount} status={self.status}>"
