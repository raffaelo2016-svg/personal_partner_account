"""Фикстуры для тестов чата."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.partner import Partner
from app.models.user import User
from tests.conftest import async_session_test


@pytest.fixture
async def partner_user():
    """Создаёт партнёра + пользователя в тестовой БД."""
    async with async_session_test() as session:
        user = User(
            email="chat_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        partner = Partner(
            user_id=user.id,
            company_name="Chat Co",
            director_name="Иванов Иван",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.commit()
        await session.refresh(user)
        await session.refresh(partner)
    return user, partner


@pytest.fixture
async def partner_user2():
    """Второй партнёр для тестов изоляции."""
    async with async_session_test() as session:
        user = User(
            email="chat_partner2@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        partner = Partner(
            user_id=user.id,
            company_name="Other Co",
            director_name="Петров Пётр",
            inn="7707654321",
            phone="+79876543210",
            status="active",
        )
        session.add(partner)
        await session.commit()
        await session.refresh(user)
        await session.refresh(partner)
    return user, partner


@pytest.fixture
async def admin_user():
    """Создаёт админа в тестовой БД."""
    async with async_session_test() as session:
        user = User(
            email="chat_admin@test.com",
            hashed_password=hash_password("admin123"),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def login_user(client: AsyncClient, email: str, password: str) -> str:
    """Логинит пользователя и возвращает access_token."""
    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]


@pytest.fixture
async def partner_token(client: AsyncClient, partner_user):
    """Access-token партнёра."""
    return await login_user(client, "chat_partner@test.com", "password123")


@pytest.fixture
async def partner_token2(client: AsyncClient, partner_user2):
    """Access-token второго партнёра."""
    return await login_user(client, "chat_partner2@test.com", "password123")


@pytest.fixture
async def admin_token(client: AsyncClient, admin_user):
    """Access-token админа."""
    return await login_user(client, "chat_admin@test.com", "admin123")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def partner_with_rooms(client: AsyncClient, partner_token):
    """Гарантирует что комнаты партнёра созданы (включая admin). Возвращает token."""
    await client.get("/api/v1/chat/rooms", headers=auth(partner_token))
    return partner_token


@pytest.fixture
async def partner2_with_rooms(client: AsyncClient, partner_token2):
    """Гарантирует что комнаты второго партнёра созданы. Возвращает token."""
    await client.get("/api/v1/chat/rooms", headers=auth(partner_token2))
    return partner_token2
