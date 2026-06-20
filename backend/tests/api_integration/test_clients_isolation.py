"""Изоляция клиентов между партнёрами."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestClientsIsolation:
    async def test_cannot_get_other_client(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token, full_name="Чужой клиент")
        resp = await client.get(f"/api/v1/clients/{c['id']}", headers=auth(partner_token2))
        assert resp.status_code == 404

    async def test_cannot_update_other_client(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        resp = await client.put(
            f"/api/v1/clients/{c['id']}",
            json={"full_name": "Hacked"},
            headers=auth(partner_token2),
        )
        assert resp.status_code == 404

    async def test_cannot_delete_other_client(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        resp = await client.delete(f"/api/v1/clients/{c['id']}", headers=auth(partner_token2))
        assert resp.status_code == 404

    async def test_cannot_change_other_status(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        resp = await client.post(
            f"/api/v1/clients/{c['id']}/status",
            json={"status": "documents_formation"},
            headers=auth(partner_token2),
        )
        assert resp.status_code == 404

    async def test_admin_can_see_all(self, client: AsyncClient, partner_token, partner_token2, admin_token):
        await create_client(client, partner_token, full_name="От партнёра 1")
        await create_client(client, partner_token2, full_name="От партнёра 2")
        resp = await client.get("/api/v1/admin/clients", headers=auth(admin_token))
        assert resp.status_code == 200
        names = [c["full_name"] for c in resp.json()["items"]]
        assert "От партнёра 1" in names
        assert "От партнёра 2" in names
