"""Полные API-тесты: Настройки партнёра + админа."""

from httpx import AsyncClient

from tests.api_integration.conftest import _login, auth


class TestPartnerTimezone:
    async def test_get_default(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/settings/timezone", headers=auth(partner_token))
        assert resp.status_code == 200
        assert "timezone" in resp.json()

    async def test_set_and_get(self, client: AsyncClient, partner_token):
        await client.put("/api/v1/settings/timezone", json={"timezone": "Asia/Tokyo"}, headers=auth(partner_token))
        data = (await client.get("/api/v1/settings/timezone", headers=auth(partner_token))).json()
        assert data["timezone"] == "Asia/Tokyo"


class TestPartnerNotifications:
    async def test_get(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/settings/notifications", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_update(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/settings/notifications", json={"email_enabled": False}, headers=auth(partner_token)
        )
        assert resp.status_code == 200


class TestPartnerChangePassword:
    async def test_success(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/settings/change-password",
            json={"current_password": "password123", "new_password": "newpass123"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        # Verify login with new password
        token = await _login(client, "integ_partner@test.com", "newpass123")
        assert token

    async def test_wrong_current(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/settings/change-password",
            json={"current_password": "wrong", "new_password": "newpass123"},
            headers=auth(partner_token),
        )
        assert resp.status_code in (400, 401, 403)


class TestAdminSettings:
    async def test_get_settings(self, client: AsyncClient, admin_token):
        resp = await client.get("/api/v1/admin/settings", headers=auth(admin_token))
        assert resp.status_code == 200

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/settings", headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_change_password(self, client: AsyncClient, admin_token):
        resp = await client.post(
            "/api/v1/admin/settings/change-password",
            json={"current_password": "admin123", "new_password": "newadmin123"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200

    async def test_login_history(self, client: AsyncClient, admin_token):
        resp = await client.get("/api/v1/admin/settings/login-history", headers=auth(admin_token))
        assert resp.status_code == 200
