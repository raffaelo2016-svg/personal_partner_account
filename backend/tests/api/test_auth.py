from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password


@pytest.fixture
async def seed_user(setup_db):
    """Create a test user directly in DB."""
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="test@example.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def admin_user(setup_db):
    """Create an admin user directly in DB."""
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="admin@test.com",
            hashed_password=hash_password("admin123"),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


class TestLogin:
    @patch("app.services.auth_service.redis_client", new_callable=AsyncMock)
    async def test_login_success(self, mock_redis, client: AsyncClient, seed_user):
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "partner"

    async def test_login_wrong_password(self, client: AsyncClient, seed_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "noone@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 401


class TestMe:
    @patch("app.services.auth_service.redis_client", new_callable=AsyncMock)
    async def test_me_authenticated(self, mock_redis, client: AsyncClient, seed_user):
        mock_redis.setex = AsyncMock()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403


class TestRefresh:
    @patch("app.services.auth_service.redis_client", new_callable=AsyncMock)
    async def test_refresh_success(self, mock_redis, client: AsyncClient, seed_user):
        mock_redis.setex = AsyncMock()
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
        )
        # refresh_token now in HttpOnly cookie, use cookie jar
        mock_redis.get = AsyncMock(return_value=str(seed_user.id))
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid.token.here",
            },
        )
        assert resp.status_code == 401


class TestLogout:
    @patch("app.services.auth_service.redis_client", new_callable=AsyncMock)
    async def test_logout(self, mock_redis, client: AsyncClient, seed_user):
        mock_redis.setex = AsyncMock()
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
        )
        # refresh_token now in HttpOnly cookie
        mock_redis.delete = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/logout",
            json={},
        )
        assert resp.status_code == 200
