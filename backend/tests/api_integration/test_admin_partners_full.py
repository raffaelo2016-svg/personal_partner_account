"""Полные API-тесты: Админ Партнёры — CRUD, фильтры, stats."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth


class TestAdminPartnersList:
    async def test_list(self, client: AsyncClient, admin_token, partner):
        resp = await client.get("/api/v1/admin/partners", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_search(self, client: AsyncClient, admin_token, partner):
        items = (
            await client.get("/api/v1/admin/partners", params={"search": "Test"}, headers=auth(admin_token))
        ).json()["items"]
        assert len(items) >= 1

    async def test_filter_status(self, client: AsyncClient, admin_token, partner):
        items = (
            await client.get("/api/v1/admin/partners", params={"status": "active"}, headers=auth(admin_token))
        ).json()["items"]
        assert all(p["status"] == "active" for p in items)

    async def test_pagination(self, client: AsyncClient, admin_token, partner, partner2):
        data = (await client.get("/api/v1/admin/partners", params={"page_size": 1}, headers=auth(admin_token))).json()
        assert len(data["items"]) == 1
        assert data["total"] >= 2

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/partners", headers=auth(partner_token))
        assert resp.status_code == 403


class TestAdminPartnerCRUD:
    async def test_get_details(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(f"/api/v1/admin/partners/{partner.id}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Test Co"

    async def test_update_status(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}", json={"status": "blocked"}, headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

    async def test_update_company_name(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}", json={"company_name": "Новое"}, headers=auth(admin_token)
        )
        assert resp.json()["company_name"] == "Новое"

    async def test_delete(self, client: AsyncClient, admin_token, partner):
        resp = await client.delete(f"/api/v1/admin/partners/{partner.id}", headers=auth(admin_token))
        assert resp.status_code == 204

    async def test_delete_nonexistent(self, client: AsyncClient, admin_token):
        resp = await client.delete(
            "/api/v1/admin/partners/00000000-0000-0000-0000-000000000000", headers=auth(admin_token)
        )
        assert resp.status_code == 404

    async def test_get_nonexistent(self, client: AsyncClient, admin_token):
        resp = await client.get(
            "/api/v1/admin/partners/00000000-0000-0000-0000-000000000000", headers=auth(admin_token)
        )
        assert resp.status_code == 404


class TestAdminPartnerStats:
    async def test_structure(self, client: AsyncClient, admin_token, partner):
        resp = await client.get("/api/v1/admin/partners/stats", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/partners/stats", headers=auth(partner_token))
        assert resp.status_code == 403
