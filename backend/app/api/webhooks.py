"""Публичные webhook-эндпоинты внешних сервисов (без auth)."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.finance_service import handle_yookassa_event
from app.services.yookassa_service import is_yookassa_ip
from app.services.telegram_service import connect_chat_from_start, disconnect_chat, send_telegram_message
import secrets

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram", status_code=200)
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret or not secrets.compare_digest(supplied_secret, expected_secret):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    message = body.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    if not isinstance(chat_id, int) or chat.get("type") != "private":
        return {"ok": True}

    if text.startswith("/start "):
        token = text.split(maxsplit=1)[1].strip()
        connected = await connect_chat_from_start(
            db,
            token=token,
            chat_id=chat_id,
            username=(message.get("from") or {}).get("username"),
        )
        reply = (
            "Готово! Telegram подключён к вашему кабинету ЮРИТЕХ."
            if connected
            else "Ссылка недействительна или устарела. Создайте новую ссылку в настройках кабинета."
        )
        await send_telegram_message(chat_id, reply)
    elif text == "/stop":
        disconnected = await disconnect_chat(db, chat_id)
        reply = (
            "Telegram отключён от кабинета."
            if disconnected
            else "Этот Telegram не подключён к кабинету."
        )
        await send_telegram_message(chat_id, reply)
    elif text == "/start":
        await send_telegram_message(chat_id, "Подключите Telegram из раздела «Настройки» в кабинете ЮРИТЕХ.")

    return {"ok": True}


@router.post("/yookassa", status_code=200)
async def yookassa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    client_ip = request.client.host if request.client else ""

    # В dev-окружении (test/development) пропускаем IP-проверку, чтобы можно было
    # тестировать webhook через ngrok/curl без allow-list.
    enforce_ip = settings.ENVIRONMENT in ("production", "staging")
    if enforce_ip and not is_yookassa_ip(client_ip):
        logger.warning("yookassa_webhook_ip_rejected", ip=client_ip)
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    event = body.get("event")
    obj = body.get("object") or {}
    payment_id = obj.get("id")
    if not event or not payment_id:
        logger.warning("yookassa_webhook_invalid_payload", body=body)
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(
        "yookassa_webhook_received",
        yk_event=event,
        payment_id=payment_id,
        ip=client_ip,
    )
    try:
        await handle_yookassa_event(db, event, payment_id)
        await db.commit()
    except Exception as exc:
        import traceback

        logger.error(
            "yookassa_webhook_handler_error",
            error=str(exc),
            error_type=type(exc).__name__,
            payment_id=payment_id,
            traceback=traceback.format_exc(),
        )
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=500,
            content={"detail": "Webhook processing failed"},
        )
    return {"ok": True}
