from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.task import Task
    from app.models.user import User


class TaskFile(Base, TimestampMixin):
    """Документ, загруженный в задачу.

    Один и тот же файл виден в задаче и в карточке клиента: связь идёт через
    ``task_id``, а ``client_id`` денормализован для выборки в карточке клиента.
    """

    __tablename__ = "task_files"
    __table_args__ = (
        Index("ix_task_files_task_created", "task_id", "created_at"),
        Index("ix_task_files_client_created", "client_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True, default=None
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    original_name: Mapped[str] = mapped_column(String(500))
    s3_key: Mapped[str] = mapped_column(String(500), unique=True)
    size: Mapped[int] = mapped_column()
    mime_type: Mapped[str] = mapped_column(String(150))
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    task: Mapped[Task] = relationship("Task", back_populates="files")
    client: Mapped[Client | None] = relationship("Client")
    uploader: Mapped[User] = relationship("User")


class TaskMessage(Base, TimestampMixin):
    """Сообщение обсуждения внутри задачи (отдельно от общего чата)."""

    __tablename__ = "task_messages"
    __table_args__ = (Index("ix_task_messages_task_created", "task_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)

    task: Mapped[Task] = relationship("Task", back_populates="messages")
    author: Mapped[User] = relationship("User")


class TaskEvent(Base, TimestampMixin):
    """История задачи: создание, смена статуса, проверка, файлы."""

    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_created", "task_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))

    task: Mapped[Task] = relationship("Task", back_populates="events")
    actor: Mapped[User | None] = relationship("User")


class TaskReadState(Base):
    __tablename__ = "task_read_states"
    __table_args__ = (UniqueConstraint("user_id", "task_id", name="uq_task_read_states_user_task"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    last_read_at: Mapped[datetime] = mapped_column(UTCDateTime)
