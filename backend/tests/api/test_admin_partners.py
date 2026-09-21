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
        assert data["bitrix_sync_status"] == "not_scheduled"
        assert data["bitrix_sync_error_code"] == "INSTALLATION_NOT_FOUND"

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

    async def test_create_partner_with_one_calendar_month_promotion(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/admin/partners",
            json={
                "email": "promo-partner@test.com",
                "password": "securepass123",
                "company_name": "Promo Company",
                "director_name": "Promo Director",
                "inn": "7701234567",
                "phone": "+7 (495) 111-22-44",
                "court_fee_per_client": 1_700_000,
                "free_client_limit": 10,
                "promotion_start_date": "2026-09-07",
            },
            headers=auth_headers(admin_token),
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["court_fee_per_client"] == 1_700_000
        assert data["free_client_limit"] == 10
        assert data["promotion_start_date"] == "2026-09-07"
        assert data["promotion_end_date"] == "2026-10-07"


class TestGetPartner:
    async def test_get_partner_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/admin/partners/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 404


class TestPartnerBitrix24:
    async def _create_partner(self, client: AsyncClient, admin_token: str) -> dict:
        response = await client.post(
            "/api/v1/admin/partners",
            json={
                "email": "bitrix-partner@test.com",
                "password": "securepass123",
                "company_name": "Bitrix Test Company",
                "director_name": "Test Director",
                "inn": "7701234567",
                "phone": "+7 (495) 111-22-33",
            },
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 201
        return response.json()

    async def test_retry_reports_missing_installation_without_blocking_partner(
        self,
        client: AsyncClient,
        admin_token: str,
    ):
        partner = await self._create_partner(client, admin_token)
        response = await client.post(
            f"/api/v1/admin/partners/{partner['id']}/bitrix24/retry",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 409

        partner_response = await client.get(
            f"/api/v1/admin/partners/{partner['id']}",
            headers=auth_headers(admin_token),
        )
        assert partner_response.status_code == 200
        data = partner_response.json()
        assert data["status"] == "active"
        assert data["bitrix_sync_status"] == "not_scheduled"

    async def test_admin_can_bind_collab_identifiers(
        self,
        client: AsyncClient,
        admin_token: str,
    ):
        partner = await self._create_partner(client, admin_token)
        response = await client.put(
            f"/api/v1/admin/partners/{partner['id']}/bitrix24/collab",
            json={
                "collab_id": "collab-101",
                "chat_id": "chat-202",
                "root_folder_id": "folder-303",
            },
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bitrix_collab_status"] == "linked"
        assert data["bitrix_collab_id"] == "collab-101"
        assert data["bitrix_chat_id"] == "chat-202"
        assert data["bitrix_root_folder_id"] == "folder-303"

    async def test_admin_can_bind_chat_before_collab_identifiers(
        self,
        client: AsyncClient,
        admin_token: str,
    ):
        partner = await self._create_partner(client, admin_token)
        chat_response = await client.put(
            f"/api/v1/admin/partners/{partner['id']}/bitrix24/collab",
            json={"chat_id": "chat24522"},
            headers=auth_headers(admin_token),
        )
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert chat_data["bitrix_collab_status"] == "binding_required"
        assert chat_data["bitrix_chat_id"] == "chat24522"
        assert chat_data["bitrix_collab_id"] is None
        assert chat_data["bitrix_root_folder_id"] is None

        collab_response = await client.put(
            f"/api/v1/admin/partners/{partner['id']}/bitrix24/collab",
            json={"collab_id": "collab-101", "root_folder_id": "folder-303"},
            headers=auth_headers(admin_token),
        )
        assert collab_response.status_code == 200
        collab_data = collab_response.json()
        assert collab_data["bitrix_collab_status"] == "linked"
        assert collab_data["bitrix_chat_id"] == "chat24522"

    async def test_admin_binding_requires_an_identifier(
        self,
        client: AsyncClient,
        admin_token: str,
    ):
        partner = await self._create_partner(client, admin_token)
        response = await client.put(
            f"/api/v1/admin/partners/{partner['id']}/bitrix24/collab",
            json={},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 422


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
