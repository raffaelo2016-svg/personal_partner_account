from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import UTCDateTime


class TrainingVideo(Base, TimestampMixin):
    __tablename__ = "training_videos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    duration: Mapped[int | None] = mapped_column(Integer, default=None)
    video_url: Mapped[str] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), default=None)
    order: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<TrainingVideo {self.title}>"


class FAQ(Base, TimestampMixin):
    __tablename__ = "faqs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<FAQ {self.question[:40]}>"


class Instruction(Base, TimestampMixin):
    __tablename__ = "instructions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    steps: Mapped[dict] = mapped_column(JSON)
    order: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<Instruction {self.title}>"


class ImportantNote(Base, TimestampMixin):
    __tablename__ = "important_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50), default=None)
    order: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<ImportantNote {self.title}>"


class TrainingLessonProgress(Base):
    """Отметка «урок просмотрен» для конкретного партнёра.

    Ключ урока — стабильная строка из содержания курса на фронтенде
    (например, ``intro`` или ``finance``), а не UUID видео: так прогресс
    не ломается, если видео перезапишут или переставят.
    """

    __tablename__ = "training_lesson_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    lesson_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<TrainingLessonProgress {self.user_id}:{self.lesson_key}>"
