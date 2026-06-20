"""Admin partners: update, delete, фильтрация, поиск."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth


class TestAdminPartnersCRUD:
    async def test_get_partner_details(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(f"/api/v1/admin/partners/{partner.id}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Test Co"

    async def test_update_partner_status(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"status": "blocked"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

    async def test_update_partner_company_name(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"company_name": "Новое название"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Новое название"

    async def test_delete_partner(self, client: AsyncClient, admin_token, partner):
        resp = await client.delete(f"/api/v1/admin/partners/{partner.id}", headers=auth(admin_token))
        assert resp.status_code == 204

    async def test_delete_nonexistent(self, client: AsyncClient, admin_token):
        resp = await client.delete(
            "/api/v1/admin/partners/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_partner_cannot_access(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/partners", headers=auth(partner_token))
        assert resp.status_code == 403


class TestAdminPartnersFiltering:
    async def test_filter_by_status(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(
            "/api/v1/admin/partners",
            params={"status": "active"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(p["status"] == "active" for p in items)

    async def test_search_by_company(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(
            "/api/v1/admin/partners",
            params={"search": "Test"},
            headers=auth(admin_token),
        )
        items = resp.json()["items"]
        assert len(items) >= 1

    async def test_pagination(self, client: AsyncClient, admin_token, partner, partner2):
        resp = await client.get(
            "/api/v1/admin/partners",
            params={"page_size": 1, "page": 1},
            headers=auth(admin_token),
        )
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] >= 2
