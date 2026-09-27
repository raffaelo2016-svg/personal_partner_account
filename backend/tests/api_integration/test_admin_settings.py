"""API-интеграция: /api/v1/admin/settings/* — ручки, которые ранее не покрывались."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from tests.api_integration.conftest import auth

BASE = "/api/v1/admin/settings"


class TestAuth:
    async def test_no_token_401(self, client: AsyncClient):
        resp = await client.get(BASE)
        assert resp.status_code in (401, 403)

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get(BASE, headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_partner_forbidden_notifications(self, client: AsyncClient, partner_token):
        resp = await client.get(f"{BASE}/notifications", headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_partner_forbidden_backup(self, client: AsyncClient, partner_token):
        resp = await client.post(f"{BASE}/backup", headers=auth(partner_token))
        assert resp.status_code == 403


class TestSystemSettings:
    async def test_get_returns_defaults(self, client: AsyncClient, admin_token):
        resp = await client.get(BASE, headers=auth(admin_token))
        assert resp.status_code == 200
        keys = {s["key"] for s in resp.json()}
        assert {"system_name", "language", "timezone"}.issubset(keys)

    async def test_timezone_is_locked_to_moscow(self, client: AsyncClient, admin_token):
        resp = await client.put(
            BASE,
            headers=auth(admin_token),
            json={"settings": {"timezone": "Europe/London"}},
        )
        assert resp.status_code == 400

        resp2 = await client.get(BASE, headers=auth(admin_token))
        tz2 = next(s for s in resp2.json() if s["key"] == "timezone")
        assert tz2["value"] == "Europe/Moscow"

    async def test_update_multiple_keys(self, client: AsyncClient, admin_token):
        resp = await client.put(
            BASE,
            headers=auth(admin_token),
            json={"settings": {"system_name": "X", "language": "en"}},
        )
        assert resp.status_code == 200
        body = {s["key"]: s["value"] for s in resp.json()}
        assert body["system_name"] == "X"
        assert body["language"] == "en"

    async def test_update_empty_dict_ok(self, client: AsyncClient, admin_token):
        resp = await client.put(BASE, headers=auth(admin_token), json={"settings": {}})
        assert resp.status_code == 200


class TestNotificationPrefs:
    async def test_get_creates_default(self, client: AsyncClient, admin_token, admin_user):
        resp = await client.get(f"{BASE}/notifications", headers=auth(admin_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == str(admin_user.id)
        # Все три флага — boolean
        for key in ("email_notifications", "new_partner_notifications", "critical_events"):
            assert isinstance(body[key], bool)

    async def test_update_partial(self, client: AsyncClient, admin_token):
        resp = await client.put(
            f"{BASE}/notifications",
            headers=auth(admin_token),
            json={"email_notifications": False},
        )
        assert resp.status_code == 200
        assert resp.json()["email_notifications"] is False

    async def test_update_idempotent(self, client: AsyncClient, admin_token):
        payload = {"critical_events": False}
        r1 = await client.put(f"{BASE}/notifications", headers=auth(admin_token), json=payload)
        r2 = await client.put(f"{BASE}/notifications", headers=auth(admin_token), json=payload)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["critical_events"] == r2.json()["critical_events"] is False

    async def test_update_nones_dont_overwrite(self, client: AsyncClient, admin_token):
        """Передача null не должна трогать поле — только явные значения применяются."""
        await client.put(
            f"{BASE}/notifications",
            headers=auth(admin_token),
            json={"email_notifications": False, "critical_events": True},
        )
        resp = await client.put(
            f"{BASE}/notifications",
            headers=auth(admin_token),
            json={"critical_events": None},
        )
        assert resp.status_code == 200
        # email_notifications не сбросился
        assert resp.json()["email_notifications"] is False


class TestChangePassword:
    async def test_wrong_current(self, client: AsyncClient, admin_token):
        resp = await client.post(
            f"{BASE}/change-password",
            headers=auth(admin_token),
            json={"current_password": "wrong", "new_password": "NewPass123"},
        )
        assert resp.status_code == 400
        assert resp.json().get("code") == "BAD_REQUEST"

    async def test_new_too_short(self, client: AsyncClient, admin_token):
        resp = await client.post(
            f"{BASE}/change-password",
            headers=auth(admin_token),
            json={"current_password": "admin123", "new_password": "short"},
        )
        assert resp.status_code == 400  # Сервис валидирует длину, не pydantic
        body = resp.json()
        assert "8" in body.get("detail", "")

    async def test_success_and_relogin(self, client: AsyncClient, admin_token):
        resp = await client.post(
            f"{BASE}/change-password",
            headers=auth(admin_token),
            json={"current_password": "admin123", "new_password": "NewAdmin456"},
        )
        assert resp.status_code == 200

        # Старый пароль больше не работает
        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as r:
            r.setex = AsyncMock()
            resp_old = await client.post(
                "/api/v1/auth/login",
                json={"email": "integ_admin@test.com", "password": "admin123"},
            )
            assert resp_old.status_code == 401

            resp_new = await client.post(
                "/api/v1/auth/login",
                json={"email": "integ_admin@test.com", "password": "NewAdmin456"},
            )
            assert resp_new.status_code == 200


class TestLoginHistory:
    async def test_returns_list(self, client: AsyncClient, admin_token):
        resp = await client.get(f"{BASE}/login-history", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestBackup:
    async def test_backup_triggered(self, client: AsyncClient, admin_token):
        resp = await client.post(f"{BASE}/backup", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"
