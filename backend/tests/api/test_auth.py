from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

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


class TestPasswordReset:
    async def test_forgot_password_does_not_reveal_unknown_email(self, client: AsyncClient):
        with patch("app.services.password_reset_service.redis_client", new_callable=AsyncMock) as mock_redis:
            resp = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "unknown@example.com"},
            )

        assert resp.status_code == 200
        assert "Если аккаунт" in resp.json()["message"]
        mock_redis.setex.assert_not_awaited()

    async def test_reset_password_end_to_end(self, client: AsyncClient, seed_user):
        store: dict[str, str] = {}
        redis = AsyncMock()

        async def get(key: str):
            return store.get(key)

        async def setex(key: str, _ttl: int, value: str):
            store[key] = value

        async def delete(*keys: str):
            for key in keys:
                store.pop(key, None)

        redis.get.side_effect = get
        redis.setex.side_effect = setex
        redis.delete.side_effect = delete

        with (
            patch("app.services.password_reset_service.redis_client", redis),
            patch(
                "app.services.password_reset_service.send_password_reset_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as send_email,
        ):
            request_resp = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "test@example.com"},
            )
            assert request_resp.status_code == 200
            reset_url = send_email.await_args.args[1]
            token = parse_qs(urlparse(reset_url).query)["token"][0]

            reset_resp = await client.post(
                "/api/v1/auth/reset-password",
                json={"token": token, "password": "newpassword456"},
            )
            reused_resp = await client.post(
                "/api/v1/auth/reset-password",
                json={"token": token, "password": "another789"},
            )

        assert reset_resp.status_code == 200
        assert reused_resp.status_code == 400

        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock):
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "newpassword456"},
            )
        assert login_resp.status_code == 200

    async def test_reset_password_rejects_weak_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "x" * 64, "password": "onlyletters"},
        )
        assert resp.status_code == 422
