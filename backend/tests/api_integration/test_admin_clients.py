"""Admin clients: get, update, фильтрация."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestAdminClients:
    async def test_get_client_by_id(self, client: AsyncClient, admin_token, partner_token):
        c = await create_client(client, partner_token, full_name="Админ видит")
        resp = await client.get(f"/api/v1/admin/clients/{c['id']}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Админ видит"

    async def test_update_client(self, client: AsyncClient, admin_token, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.put(
            f"/api/v1/admin/clients/{c['id']}",
            json={"full_name": "Обновлено админом"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Обновлено админом"

    async def test_filter_by_partner_id(self, client: AsyncClient, admin_token, partner_token, partner):
        await create_client(client, partner_token, full_name="Фильтр по партнёру")
        resp = await client.get(
            "/api/v1/admin/clients",
            params={"partner_id": str(partner.id)},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 1

    async def test_search(self, client: AsyncClient, admin_token, partner_token):
        await create_client(client, partner_token, full_name="УникальныйПоиск")
        resp = await client.get(
            "/api/v1/admin/clients",
            params={"search": "УникальныйПоиск"},
            headers=auth(admin_token),
        )
        assert len(resp.json()["items"]) >= 1

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/clients", headers=auth(partner_token))
        assert resp.status_code == 403
