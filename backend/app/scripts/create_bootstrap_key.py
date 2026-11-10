"""Генерация одноразового ключа первичной настройки супер-администратора.

Использование:
    python -m app.scripts.create_bootstrap_key

Ключ печатается один раз и действует 60 минут. Хранится в базе только его хэш.
"""

import asyncio

from app.database import async_session
from app.services.admin_access_service import create_bootstrap_key


async def main() -> None:
    async with async_session() as session, session.begin():
        token, expires_at = await create_bootstrap_key(session, ttl_minutes=60)

    line = "=" * 52
    print()
    print(line)
    print("  ПЕРВЫЙ ЗАПУСК КАБИНЕТА")
    print(line)
    print(f"  Одноразовый ключ:  {token}")
    print(f"  Действует до:      {expires_at:%d.%m.%Y %H:%M} (60 минут)")
    print("  Открыть:           /setup")
    print()
    print("  Ключ печатается один раз и только здесь.")
    print("  После создания супер-администратора он сгорает.")
    print(line)
    print()


if __name__ == "__main__":
    asyncio.run(main())
