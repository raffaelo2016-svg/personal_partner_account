"""Контракт приёма задач из Битрикс24 в личный кабинет партнёра.

Схемы описывают только входящий поток: шлюз ЮРИТЕХ присылает задачу из
Битрикса и забирает изменения статусов. ЛКП ничего не знает про внутренние
идентификаторы Битрикса, кроме номера задачи, и не ходит во внешнюю сеть.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.config import settings

IntegrationStatus = Literal["new", "in_progress", "done", "rejected"]
IntegrationPriority = Literal["low", "medium", "high"]


class IntegrationPartner(BaseModel):
    """Адресат задачи.

    Основной способ — номер карточки партнёра в Битриксе (``bitrix_id``):
    менеджер прикрепляет карточку в блоке «CRM» задачи, и адресат определяется
    точно. ИНН оставлен запасным вариантом для шлюзов, которые уже его передают.
    """

    bitrix_id: int | str | None = None
    inn: str | None = Field(default=None, max_length=12)
    partner_id: str | None = Field(default=None, max_length=64)

    @field_validator("inn")
    @classmethod
    def normalize_inn(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) not in (10, 12):
            raise ValueError("ИНН должен содержать 10 или 12 цифр")
        return digits

    @field_validator("bitrix_id")
    @classmethod
    def normalize_bitrix_id(cls, value: int | str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not text.isdigit() or int(text) <= 0:
            raise ValueError("bitrix_id должен быть положительным целым числом")
        return text

    @model_validator(mode="after")
    def require_identifier(self) -> IntegrationPartner:
        if not self.bitrix_id and not self.inn:
            raise ValueError("Укажите карточку партнёра (bitrix_id) или его ИНН")
        return self


class IntegrationClient(BaseModel):
    """Клиент по задаче. Передаётся только подпись, без персональных данных."""

    name: str | None = Field(default=None, max_length=255)
    deal_id: int | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None


class IntegrationAuthor(BaseModel):
    """Постановщик задачи на стороне Битрикс24."""

    name: str = Field(min_length=1, max_length=255)
    user_id: int | str

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("Имя постановщика не может быть пустым")
        return cleaned

    @field_validator("user_id")
    @classmethod
    def normalize_user_id(cls, value: int | str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("user_id не может быть пустым")
        return text


class IncomingTask(BaseModel):
    """Тело POST /api/integration/tasks."""

    bitrix_task_id: int = Field(gt=0)
    bitrix_url: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    deadline: AwareDatetime | None = None
    priority: IntegrationPriority = "medium"
    status: IntegrationStatus
    partner: IntegrationPartner
    client: IntegrationClient | None = None
    author: IntegrationAuthor
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("Заголовок задачи не может быть пустым")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("bitrix_url")
    @classmethod
    def require_bitrix_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        allowed = settings.BITRIX_ALLOWED_DOMAIN.lower()
        if parsed.scheme != "https":
            raise ValueError("Ссылка на задачу должна быть https")
        if not parsed.netloc or (allowed and parsed.hostname != allowed):
            raise ValueError(f"Ссылка на задачу должна вести на {allowed}")
        return value.strip()

    @field_validator("deadline", "created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC)


class IncomingTaskAccepted(BaseModel):
    lkp_task_id: str
    status: IntegrationStatus


class TaskStatusChangeRead(BaseModel):
    """Одно изменение статуса для шлюза."""

    bitrix_task_id: int
    lkp_task_id: str
    status: IntegrationStatus
    changed_at: datetime
    author_name: str
    reject_reason: str | None = None


class TaskStatusChanges(BaseModel):
    items: list[TaskStatusChangeRead]
    next_since: datetime


class IntegrationError(BaseModel):
    """Тело ошибки: код из ТЗ плюс человеческое пояснение."""

    error: str
    detail: str | None = None


def parse_since(value: str) -> datetime:
    """Разбор query-параметра ``since`` с обязательным часовым поясом."""
    # Незакодированный «+» в часовом поясе приходит пробелом — принимаем и так.
    normalized = value.strip().replace(" ", "+").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("since должен быть в формате ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("since должен содержать часовой пояс")
    return parsed.astimezone(UTC)
