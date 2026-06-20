"""Partner dashboard: структура ответа, доступ."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestPartnerDashboard:
    async def test_dashboard_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/dashboard", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        assert "urgent_tasks" in data
        assert "task_completion" in data
        assert "recent_clients" in data

    async def test_dashboard_with_data(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Dashboard Client")
        resp = await client.get("/api/v1/dashboard", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["stats"]["total_clients"] >= 1

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard")
        assert resp.status_code in (401, 403)
