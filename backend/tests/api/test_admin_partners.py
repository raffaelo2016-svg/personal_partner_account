from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password


@pytest.fixture
async def admin_token(client: AsyncClient, setup_db):
    """Create admin user and return access token."""
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

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "admin123",
            },
        )
        return resp.json()["access_token"]


@pytest.fixture
async def partner_token(client: AsyncClient, setup_db):
    """Create partner user and return access token."""
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="partner@test.com",
            hashed_password=hash_password("partner123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.commit()

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "partner@test.com",
                "password": "partner123",
            },
        )
        return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestListPartners:
    async def test_list_partners_as_admin(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/admin/partners", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_partners_forbidden_for_partner(self, client: AsyncClient, partner_token: str):
        resp = await client.get("/api/v1/admin/partners", headers=auth_headers(partner_token))
        assert resp.status_code == 403

    async def test_list_partners_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/partners")
        assert resp.status_code == 403


class TestCreatePartner:
    async def test_create_partner_success(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/admin/partners",
            json={
                "email": "new-partner@test.com",
                "password": "securepass123",
                "company_name": "Test Company",
                "director_name": "Test Director",
                "inn": "7701234567",
                "phone": "+7 (495) 111-22-33",
            },
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "Test Company"
        assert data["status"] == "active"

    async def test_create_partner_duplicate_email(self, client: AsyncClient, admin_token: str):
        payload = {
            "email": "dup@test.com",
            "password": "securepass123",
            "company_name": "Company A",
            "director_name": "Director A",
            "inn": "7701234567",
            "phone": "+7 (495) 111-22-33",
        }
        await client.post("/api/v1/admin/partners", json=payload, headers=auth_headers(admin_token))
        resp = await client.post("/api/v1/admin/partners", json=payload, headers=auth_headers(admin_token))
        assert resp.status_code == 409


class TestGetPartner:
    async def test_get_partner_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/admin/partners/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404


class TestPartnerStats:
    async def test_stats_as_admin(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/admin/partners/stats", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_partners" in data
        assert "active_partners" in data

    async def test_stats_forbidden_for_partner(self, client: AsyncClient, partner_token: str):
        resp = await client.get("/api/v1/admin/partners/stats", headers=auth_headers(partner_token))
        assert resp.status_code == 403
