"""Тонкая обёртка над официальным SDK ЮKassa."""

from __future__ import annotations

import ipaddress
import uuid
from typing import Any

import structlog
from yookassa import Configuration, Payment

from app.config import settings

logger = structlog.get_logger()

# Список IP-адресов, с которых ЮKassa отправляет webhook-уведомления.
# https://yookassa.ru/developers/using-api/webhooks
YOOKASSA_IP_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.156.11/32"),
    ipaddress.ip_network("77.75.156.35/32"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180:0::/32"),
]

_initialized = False


def init_yookassa() -> bool:
    """Сконфигурировать SDK. Возвращает True, если ключи заданы."""
    global _initialized
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        logger.warning("yookassa_not_configured")
        return False
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    _initialized = True
    logger.info("yookassa_initialized", shop_id=settings.YOOKASSA_SHOP_ID)
    return True


def is_configured() -> bool:
    return _initialized


def is_yookassa_ip(ip: str) -> bool:
    """Проверка, что webhook пришёл с IP ЮKassa."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in YOOKASSA_IP_NETWORKS)


def _format_amount(cents: int) -> str:
    rub = cents // 100
    kop = cents % 100
    return f"{rub}.{kop:02d}"


def create_payment(
    amount_cents: int,
    return_url: str,
    description: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Создаёт платёж в ЮKassa с redirect-подтверждением через ЮMoney."""
    if not _initialized:
        raise RuntimeError("YooKassa is not configured")

    idem_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": _format_amount(amount_cents), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description[:128],
        "payment_method_data": {"type": "yoo_money"},
        "metadata": metadata,
    }
    payment = Payment.create(payload, idem_key)
    logger.info(
        "yookassa_payment_created",
        payment_id=payment.id,
        amount_cents=amount_cents,
        idempotence_key=idem_key,
    )
    return {
        "id": payment.id,
        "status": payment.status,
        "confirmation_url": payment.confirmation.confirmation_url if payment.confirmation else None,
    }


def fetch_payment(payment_id: str) -> dict[str, Any]:
    """Получить актуальный статус платежа из ЮKassa."""
    if not _initialized:
        raise RuntimeError("YooKassa is not configured")
    payment = Payment.find_one(payment_id)
    return {
        "id": payment.id,
        "status": payment.status,
        "paid": getattr(payment, "paid", False),
        "amount": payment.amount.value if payment.amount else None,
        "metadata": payment.metadata or {},
    }
