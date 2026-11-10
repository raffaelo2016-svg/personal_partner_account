"""Проверка настройки почты для приглашений и сброса пароля.

Запуск:
    python -m app.scripts.check_email --to someone@uritech.ru
    python -m app.scripts.check_email            # только показать конфигурацию
"""

import argparse
import asyncio
import sys

from app.config import settings
from app.services.email_service import send_test_email


def _mask(value: str) -> str:
    if not value:
        return "—"
    if "@" in value:
        name, domain = value.split("@", 1)
        return f"{name[:2]}***@{domain}"
    return f"{value[:2]}***"


def describe() -> str:
    if settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL:
        return f"Resend, отправитель {_mask(settings.RESEND_FROM_EMAIL)}"
    if settings.SMTP_HOST and (settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME):
        mode = "SSL" if settings.SMTP_USE_SSL else "STARTTLS" if settings.SMTP_USE_STARTTLS else "plain"
        return (
            f"SMTP {settings.SMTP_HOST}:{settings.SMTP_PORT} ({mode}), "
            f"отправитель {_mask(settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME)}"
        )
    return "не настроено"


async def _run(recipient: str | None) -> int:
    print(f"Почта: {describe()}")
    print(f"Публичный адрес кабинета: {settings.PUBLIC_APP_URL}")

    if not recipient:
        if describe() == "не настроено":
            print("Задайте RESEND_* или SMTP_* в .env — иначе приглашения и сброс пароля не уходят.")
            return 1
        print("Чтобы отправить тестовое письмо: --to адрес@example.ru")
        return 0

    delivered, transport = await send_test_email(recipient)
    if delivered:
        print(f"Письмо отправлено через {transport} на {recipient}.")
        print("Проверьте входящие и папку «Спам».")
        return 0

    print(f"Не удалось отправить: {transport}.")
    if transport == "not_configured":
        print("Заполните RESEND_API_KEY и RESEND_FROM_EMAIL или SMTP_HOST/SMTP_* в .env.")
    else:
        print("Проверьте хост, порт, логин и пароль приложения, затем повторите.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка почты для приглашений")
    parser.add_argument("--to", help="адрес для тестового письма")
    args = parser.parse_args()
    return asyncio.run(_run(args.to))


if __name__ == "__main__":
    sys.exit(main())
