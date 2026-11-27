"""HTTP-контракт интеграции «Битрикс24 -> ЛКП» из ТЗ (разделы 8 и 9).

Эндпоинты закрыты отдельным токеном шлюза, а не пользовательской сессией:
кабинет не умеет ходить во внешнюю сеть, поэтому обмен инициирует шлюз.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.schemas.bitrix_task_integration import (
    IncomingTask,
    parse_since,
)
from app.services.bitrix_task_integration import IntegrationError, list_status_changes, receive_task

logger = structlog.get_logger()
MOSCOW = ZoneInfo("Europe/Moscow")

router = APIRouter(prefix="/integration", tags=["bitrix-integration"])


def _iso(value: datetime) -> str:
    return value.astimezone(MOSCOW).isoformat()


async def require_integration_token(
    x_integration_token: str | None = Header(default=None, alias="X-Integration-Token"),
) -> None:
    """Проверка токена шлюза. Пустой токен в настройках выключает приём."""
    expected = settings.BITRIX_INTEGRATION_TOKEN.strip()
    if not expected:
        raise IntegrationError(
            503,
            "integration_disabled",
            "Приём задач из Битрикс24 не настроен: BITRIX_INTEGRATION_TOKEN пуст",
        )
    if not x_integration_token or not compare_tokens(x_integration_token, expected):
        raise IntegrationError(401, "unauthorized", "Неверный X-Integration-Token")


def compare_tokens(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.strip(), expected)


@router.post("/tasks", dependencies=[Depends(require_integration_token)])
@limiter.limit(settings.BITRIX_INTEGRATION_RATE_LIMIT)
async def receive_task_endpoint(
    request: Request,
    payload: IncomingTask,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> JSONResponse:
    """Создать или обновить задачу из Битрикс24.

    201 — задача создана, 200 — уже была и обновлена (или повтор без изменений).
    """
    if not idempotency_key or not idempotency_key.strip():
        raise IntegrationError(400, "invalid_payload", "Заголовок Idempotency-Key обязателен")
    if len(idempotency_key) > 200:
        raise IntegrationError(400, "invalid_payload", "Idempotency-Key слишком длинный")

    result = await receive_task(db, payload)
    await db.commit()
    return JSONResponse(
        status_code=201 if result.created else 200,
        content={
            "lkp_task_id": str(result.task.id),
            "status": result.task.bitrix_status or "new",
        },
    )


@router.get("/tasks/changes", dependencies=[Depends(require_integration_token)])
@limiter.limit(settings.BITRIX_INTEGRATION_RATE_LIMIT)
async def list_changes_endpoint(
    request: Request,
    since: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> JSONResponse:
    """Изменения статусов со стороны партнёра для применения в Битриксе.

    Без ``since`` ничего не отдаём и возвращаем текущее время: случайный
    пустой запрос не должен выливать шлюзу всю историю.
    """
    if since is None or not since.strip():
        return JSONResponse(
            content={"items": [], "next_since": _iso(datetime.now(UTC))},
        )
    try:
        since_dt = parse_since(since)
    except ValueError as exc:
        raise IntegrationError(400, "invalid_payload", str(exc)) from exc

    items, next_since = await list_status_changes(db, since=since_dt, limit=limit)
    return JSONResponse(
        content={
            "items": [
                {
                    "bitrix_task_id": item.bitrix_task_id,
                    "lkp_task_id": item.lkp_task_id,
                    "status": item.status,
                    "changed_at": _iso(item.changed_at),
                    "author_name": item.author_name,
                    "reject_reason": item.reject_reason,
                }
                for item in items
            ],
            "next_since": _iso(next_since),
        }
    )
