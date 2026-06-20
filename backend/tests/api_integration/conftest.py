"""Общие фикстуры для интеграционных API-тестов."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.partner import Partner
from app.models.user import User
from tests.conftest import async_session_test


async def _create_user(email: str, password: str, role: str, is_active: bool = True) -> User:
    async with async_session_test() as session:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _create_partner(user: User, *, status: str = "active", company_name: str = "Test Co") -> Partner:
    async with async_session_test() as session:
        partner = Partner(
            user_id=user.id,
            company_name=company_name,
            director_name="Директор",
            inn="7701234567",
            phone="+71234567890",
            status=status,
        )
        session.add(partner)
        await session.commit()
        await session.refresh(partner)
    return partner


async def _login(client: AsyncClient, email: str, password: str) -> str:
    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Partner fixtures ──


@pytest.fixture
async def partner_user():
    return await _create_user("integ_partner@test.com", "password123", "partner")


@pytest.fixture
async def partner(partner_user):
    return await _create_partner(partner_user)


@pytest.fixture
async def partner_token(client, partner):
    return await _login(client, "integ_partner@test.com", "password123")


@pytest.fixture
async def partner_user2():
    return await _create_user("integ_partner2@test.com", "password123", "partner")


@pytest.fixture
async def partner2(partner_user2):
    return await _create_partner(partner_user2, company_name="Other Co")


@pytest.fixture
async def partner_token2(client, partner2):
    return await _login(client, "integ_partner2@test.com", "password123")


# ── Admin fixture ──


@pytest.fixture
async def admin_user():
    return await _create_user("integ_admin@test.com", "admin123", "admin")


@pytest.fixture
async def admin_token(client, admin_user):
    return await _login(client, "integ_admin@test.com", "admin123")


# ── Helper: create client ──


async def create_client(
    client: AsyncClient,
    token: str,
    *,
    full_name: str = "Иванов Иван",
    client_type: str = "before_court",
) -> dict:
    resp = await client.post(
        "/api/v1/clients",
        json={"type": client_type, "full_name": full_name, "phone": "+79001112233"},
        headers=auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_task(
    client: AsyncClient,
    token: str,
    client_id: str,
    *,
    title: str = "Тестовая задача",
    priority: str = "medium",
) -> dict:
    resp = await client.post(
        "/api/v1/tasks",
        json={
            "client_id": client_id,
            "title": title,
            "priority": priority,
            "due_date": str(date.today() + timedelta(days=7)),
        },
        headers=auth(token),
    )
    assert resp.status_code == 201
    return resp.json()
