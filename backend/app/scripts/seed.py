"""Скрипт для создания администратора через терминал."""

import asyncio
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.database import async_session
from app.models.user import User


def _clean_input(raw: str) -> str:
    """Убирает суррогатные символы, которые macOS-терминал может добавить ко вводу."""
    return raw.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="ignore").strip()


async def create_admin_interactive() -> None:
    print("=== Создание администратора ===")
    email = _clean_input(input("Email: "))
    if not email:
        print("Ошибка: email не может быть пустым")
        return

    password = _clean_input(getpass.getpass("Пароль: "))
    if len(password) < 6:
        print("Ошибка: пароль должен содержать минимум 6 символов")
        return

    password_confirm = _clean_input(getpass.getpass("Подтвердите пароль: "))
    if password != password_confirm:
        print("Ошибка: пароли не совпадают")
        return

    async with async_session() as session, session.begin():
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"Пользователь с email {email} уже существует")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()

    print(f"Администратор {email} успешно создан")


def main() -> None:
    asyncio.run(create_admin_interactive())


if __name__ == "__main__":
    main()
