"""Полные API-тесты: Дашборды партнёра и админа."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestPartnerDashboard:
    async def test_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/dashboard", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        assert "urgent_tasks" in data
        assert "task_completion" in data
        assert "recent_clients" in data

    async def test_stats_fields(self, client: AsyncClient, partner_token):
        data = (await client.get("/api/v1/dashboard", headers=auth(partner_token))).json()["stats"]
        for key in ("total_clients", "new_this_week", "before_court", "in_court", "completed"):
            assert key in data

    async def test_with_data(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token)
        data = (await client.get("/api/v1/dashboard", headers=auth(partner_token))).json()
        assert data["stats"]["total_clients"] >= 1

    async def test_recent_clients(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Недавний")
        recent = (await client.get("/api/v1/dashboard", headers=auth(partner_token))).json()["recent_clients"]
        assert isinstance(recent, list)

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard")
        assert resp.status_code in (401, 403)


class TestAdminDashboard:
    async def test_structure(self, client: AsyncClient, admin_token, partner_token):
        resp = await client.get("/api/v1/admin/dashboard", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "main_stats" in data
        assert "movement_stats" in data
        assert "finance_stats" in data
        assert "top_partners" in data

    async def test_main_stats_fields(self, client: AsyncClient, admin_token, partner_token):
        data = (await client.get("/api/v1/admin/dashboard", headers=auth(admin_token))).json()
        assert isinstance(data["main_stats"], dict)
        assert isinstance(data["top_partners"], list)

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/dashboard", headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/dashboard")
        assert resp.status_code in (401, 403)
