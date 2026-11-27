from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime


class BitrixTaskStatusChange(Base, TimestampMixin):
    """История смены статуса задачи в рамках интеграции с Битрикс24.

    Отдельная таблица, а не событие задачи: шлюз забирает изменения по
    ``changed_at`` и не должен видеть эхо собственных обновлений. Поэтому
    сюда попадают только изменения со стороны кабинета (``origin='cabinet'``),
    и запись переживает потерю ``next_since`` на стороне шлюза.
    """

    __tablename__ = "bitrix_task_status_changes"
    __table_args__ = (
        Index("ix_bitrix_task_status_changes_changed", "changed_at"),
        Index("ix_bitrix_task_status_changes_task", "task_id", "changed_at"),
        Index("ix_bitrix_task_status_changes_remote", "bitrix_task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    bitrix_task_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    author_name: Mapped[str] = mapped_column(String(255))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    reject_reason: Mapped[str | None] = mapped_column(Text, default=None)
    origin: Mapped[str] = mapped_column(String(20), default="cabinet")


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
        Index(
            "ix_bitrix_inbound_events_remote",
            "member_id",
            "remote_entity_type",
            "remote_entity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("bitrix_installations.member_id", ondelete="CASCADE"),
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(64))
    event_name: Mapped[str] = mapped_column(String(100))
    remote_entity_type: Mapped[str | None] = mapped_column(String(50), default=None)
    remote_entity_id: Mapped[str | None] = mapped_column(String(100), default=None)
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
