"""Auth edge cases: inactive user, pending/blocked partner, expired token, register validation."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from tests.api_integration.conftest import _create_partner, _create_user, auth


class TestLoginEdgeCases:
    async def test_login_inactive_user(self, client: AsyncClient):
        await _create_user("inactive@test.com", "password123", "partner", is_active=False)
        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as r:
            r.setex = AsyncMock()
            resp = await client.post(
                "/api/v1/auth/login", json={"email": "inactive@test.com", "password": "password123"}
            )
        assert resp.status_code == 401

    async def test_login_pending_partner(self, client: AsyncClient):
        user = await _create_user("pending@test.com", "password123", "partner")
        await _create_partner(user, status="pending")
        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as r:
            r.setex = AsyncMock()
            resp = await client.post(
                "/api/v1/auth/login", json={"email": "pending@test.com", "password": "password123"}
            )
        assert resp.status_code == 403
        assert resp.json()["code"] == "PARTNER_PENDING"

    async def test_login_blocked_partner(self, client: AsyncClient):
        user = await _create_user("blocked@test.com", "password123", "partner")
        await _create_partner(user, status="blocked")
        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as r:
            r.setex = AsyncMock()
            resp = await client.post(
                "/api/v1/auth/login", json={"email": "blocked@test.com", "password": "password123"}
            )
        assert resp.status_code == 403
        assert resp.json()["code"] == "PARTNER_BLOCKED"

    async def test_login_wrong_password(self, client: AsyncClient):
        await _create_user("wrongpw@test.com", "password123", "partner")
        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as r:
            r.setex = AsyncMock()
            resp = await client.post("/api/v1/auth/login", json={"email": "wrongpw@test.com", "password": "wrong"})
        assert resp.status_code == 401

    async def test_me_no_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    async def test_me_invalid_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me", headers=auth("invalid.token.here"))
        assert resp.status_code in (401, 403)


class TestRegisterEdgeCases:
    async def test_register_missing_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={"email": "x@x.com"})
        assert resp.status_code == 422

    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@test.com",
                "password": "123",
                "company_name": "Co",
                "director_name": "Dir",
                "inn": "7701234567",
                "phone": "+71234567890",
            },
        )
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "company_name": "Co",
                "director_name": "Dir",
                "inn": "7701234567",
                "phone": "+71234567890",
            },
        )
        assert resp.status_code == 422
