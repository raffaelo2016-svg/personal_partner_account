"""Yandex SmartCaptcha — верификация токена с формы регистрации."""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

_VALIDATE_URL = "https://smartcaptcha.yandexcloud.net/validate"


async def verify_captcha(token: str, ip: str | None) -> bool:
    """Проверить токен через Yandex SmartCaptcha API.

    Если секрет не задан (dev, test, staging без включённой капчи) —
    возвращаем True, чтобы не ломать окружения без настроенного ключа.

    Формат запроса по документации Yandex — GET с query-string:
    https://yandex.cloud/ru/docs/smartcaptcha/concepts/validation
    """
    if not settings.YANDEX_CAPTCHA_SECRET_KEY:
        return True
    params = {
        "secret": settings.YANDEX_CAPTCHA_SECRET_KEY,
        "token": token,
        "ip": ip or "",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(_VALIDATE_URL, params=params)
    except httpx.HTTPError as exc:
        # Fail-closed: Yandex API недоступен → не пускаем. Для «хотя бы как-то
        # работает» решение — ручная модерация партнёров админом всё равно
        # держит ботов снаружи приложения, так что fail-closed здесь безопаснее.
        logger.warning("captcha_verify_http_error", error=str(exc))
        return False
    if resp.status_code != 200:
        logger.warning("captcha_verify_non_200", status=resp.status_code, body=resp.text[:200])
        return False
    data = resp.json()
    return data.get("status") == "ok"
