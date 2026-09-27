"""Partner settings: timezone, notifications, change password."""

from httpx import AsyncClient

from tests.api_integration.conftest import _login, auth


class TestTimezone:
    async def test_get_timezone(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/settings/timezone", headers=auth(partner_token))
        assert resp.status_code == 200
        assert "timezone" in resp.json()

    async def test_timezone_is_locked_to_moscow(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/settings/timezone",
            json={"timezone": "Asia/Tokyo"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 400

        resp2 = await client.get("/api/v1/settings/timezone", headers=auth(partner_token))
        assert resp2.json()["timezone"] == "Europe/Moscow"


class TestNotificationPrefs:
    async def test_get_notification_prefs(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/settings/notifications", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_update_notification_prefs(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/settings/notifications",
            json={"email_enabled": False},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200


class TestChangePassword:
    async def test_change_password_success(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/settings/change-password",
            json={"current_password": "password123", "new_password": "newpassword123"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200

        # Логин с новым паролем
        token = await _login(client, "integ_partner@test.com", "newpassword123")
        assert token

    async def test_change_password_wrong_current(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/settings/change-password",
            json={"current_password": "wrong", "new_password": "newpassword123"},
            headers=auth(partner_token),
        )
        assert resp.status_code in (400, 401, 403)
