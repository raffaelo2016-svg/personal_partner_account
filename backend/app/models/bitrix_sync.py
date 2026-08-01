from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime


class BitrixEntityMap(Base, TimestampMixin):
    """Stable link between one cabinet object and one Bitrix24 object."""

    __tablename__ = "bitrix_entity_maps"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "local_entity_type",
            "local_entity_id",
            name="uq_bitrix_entity_maps_local",
        ),
        UniqueConstraint(
            "member_id",
            "bitrix_entity_type",
            "bitrix_entity_id",
            name="uq_bitrix_entity_maps_remote",
        ),
        Index("ix_bitrix_entity_maps_verification", "member_id", "last_verified_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("bitrix_installations.member_id", ondelete="CASCADE"),
        index=True,
    )
    local_entity_type: Mapped[str] = mapped_column(String(50))
    local_entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    bitrix_entity_type: Mapped[str] = mapped_column(String(50))
    bitrix_entity_id: Mapped[str] = mapped_column(String(100))
    sync_version: Mapped[int] = mapped_column(default=1)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class BitrixInboundEvent(Base, TimestampMixin):
    """Credential-free receipt used to deduplicate Bitrix24 events."""

    __tablename__ = "bitrix_inbound_events"
    __table_args__ = (
        UniqueConstraint("member_id", "event_key", name="uq_bitrix_inbound_events_key"),
        CheckConstraint(
            "status IN ('received', 'processing', 'completed', 'failed', 'ignored')",
            name="ck_bitrix_inbound_events_status",
        ),
        Index("ix_bitrix_inbound_events_work", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("bitrix_installations.member_id", ondelete="CASCADE"),
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(64))
    event_name: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="received")
    attempts: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class BitrixOutboxOperation(Base, TimestampMixin):
    """Durable outgoing Bitrix24 operation with bounded retries."""

    __tablename__ = "bitrix_outbox_operations"
    __table_args__ = (
        UniqueConstraint("member_id", "operation_key", name="uq_bitrix_outbox_operation_key"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'retry', 'failed')",
            name="ck_bitrix_outbox_operations_status",
        ),
        Index("ix_bitrix_outbox_ready", "status", "next_attempt_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("bitrix_installations.member_id", ondelete="CASCADE"),
        index=True,
    )
    operation_key: Mapped[str] = mapped_column(String(160))
    local_entity_type: Mapped[str] = mapped_column(String(50))
    local_entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    bitrix_method: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    correlation_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=8)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    result_reference: Mapped[str | None] = mapped_column(Text, default=None)
