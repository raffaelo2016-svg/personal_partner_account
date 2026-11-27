from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.partner import Partner
    from app.models.task_workspace import TaskEvent, TaskFile, TaskMessage
    from app.models.user import User


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "bitrix_sync_status IN ('not_scheduled', 'pending', 'processing', 'synced', 'failed')",
            name="ck_tasks_bitrix_sync_status",
        ),
        Index("ix_tasks_bitrix_sync_status", "bitrix_sync_status"),
        # Задача, пришедшая из Битрикса через шлюз, уникальна по номеру задачи:
        # повторная доставка обновляет её, а не создаёт вторую.
        Index(
            "uq_tasks_gateway_bitrix_task_id",
            "bitrix_task_id",
            unique=True,
            postgresql_where=text("origin = 'bitrix_gateway'"),
            sqlite_where=text("origin = 'bitrix_gateway'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id"), index=True, default=None)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), index=True, default=None)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    assigned_to: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(index=True, default=None)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    review_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None, index=True)
    review_requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    bitrix_sync_status: Mapped[str] = mapped_column(String(20), default="not_scheduled")
    bitrix_sync_error_code: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_task_id: Mapped[str | None] = mapped_column(String(100), default=None)
    bitrix_imported: Mapped[bool] = mapped_column(default=False)
    bitrix_published: Mapped[bool] = mapped_column(default=True)
    bitrix_sync_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # Диалог чата задачи в Битрикс24 (``chat<ID>``). Через него идёт обсуждение
    # задачи: сообщения из кабинета уходят в чат, ответы из Битрикс24 — обратно.
    bitrix_chat_dialog_id: Mapped[str | None] = mapped_column(String(50), default=None)

    # Происхождение задачи: "cabinet" — создана в кабинете, "bitrix_gateway" —
    # пришла от шлюза по ТЗ «Передача задач из Битрикс24 в ЛКП».
    origin: Mapped[str] = mapped_column(String(20), default="cabinet", server_default="cabinet")
    # Адресат и автор на стороне Битрикс24: ссылку партнёру не показываем,
    # она нужна только интеграции.
    bitrix_url: Mapped[str | None] = mapped_column(String(500), default=None)
    bitrix_author_name: Mapped[str | None] = mapped_column(String(255), default=None)
    bitrix_author_id: Mapped[str | None] = mapped_column(String(50), default=None)
    # Клиент по задаче приходит из Битрикса подписью; локальная карточка клиента
    # привязывается только при точном совпадении сделки и партнёра.
    bitrix_client_name: Mapped[str | None] = mapped_column(String(255), default=None)
    bitrix_deal_id: Mapped[str | None] = mapped_column(String(100), default=None)
    # Последний статус из Битрикса (new / in_progress / done / rejected) и
    # момент изменения на его стороне — по нему разрешаются конфликты.
    bitrix_status: Mapped[str | None] = mapped_column(String(20), default=None)
    bitrix_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    reject_reason: Mapped[str | None] = mapped_column(Text, default=None)
    status_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    partner: Mapped[Partner | None] = relationship("Partner")
    client: Mapped[Client | None] = relationship("Client")
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[review_requested_by])
    files: Mapped[list[TaskFile]] = relationship("TaskFile", back_populates="task", cascade="all, delete-orphan")
    messages: Mapped[list[TaskMessage]] = relationship(
        "TaskMessage", back_populates="task", cascade="all, delete-orphan"
    )
    events: Mapped[list[TaskEvent]] = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Task {self.title} status={self.status}>"
