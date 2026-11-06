"""Учёт неудачных попыток входа: капча и временная блокировка.

Счётчик хранится в Redis по паре «идентификатор + IP» и живёт 15 минут.
После 3 неудач требуется капча, после 5 — вход временно блокируется.
"""

import hashlib

import structlog

from app.core.redis import redis_client

logger = structlog.get_logger()

WINDOW_SECONDS = 15 * 60
CAPTCHA_THRESHOLD = 3
LOCK_THRESHOLD = 5


def _key(identifier: str, ip: str | None) -> str:
    digest = hashlib.sha256(f"{identifier.strip().lower()}|{ip or 'unknown'}".encode()).hexdigest()
    return f"login_fail:{digest}"


async def get_failures(identifier: str, ip: str | None) -> int:
    value = await redis_client.get(_key(identifier, ip))
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


async def register_failure(identifier: str, ip: str | None) -> int:
    key = _key(identifier, ip)
    count = await redis_client.incr(key)
    await redis_client.expire(key, WINDOW_SECONDS)
    logger.warning("login_failure_registered", failures=count)
    return int(count)


async def clear_failures(identifier: str, ip: str | None) -> None:
    await redis_client.delete(_key(identifier, ip))
