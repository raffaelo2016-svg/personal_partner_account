from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_admin(client: AsyncClient, setup_db):
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="settings_admin@test.com",
            hashed_password=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "settings_admin@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestAdminSettings:
    async def test_get_settings(self, client: AsyncClient, setup_db):
        token = await _setup_admin(client, setup_db)
        resp = await client.get(
            "/api/v1/admin/settings",
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        keys = {s["key"] for s in data}
        assert "system_name" in keys

    async def test_update_settings(self, client: AsyncClient, setup_db):
        token = await _setup_admin(client, setup_db)
        resp = await client.put(
            "/api/v1/admin/settings",
            headers=auth(token),
            json={"settings": {"system_name": "New Name"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        updated = {s["key"]: s["value"] for s in data}
        assert updated["system_name"] == "New Name"

    async def test_notification_prefs(self, client: AsyncClient, setup_db):
        token = await _setup_admin(client, setup_db)
        resp = await client.get(
            "/api/v1/admin/settings/notifications",
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_notifications"] is True

    async def test_update_notification_prefs(
        self,
        client: AsyncClient,
        setup_db,
    ):
        token = await _setup_admin(client, setup_db)
        resp = await client.put(
            "/api/v1/admin/settings/notifications",
            headers=auth(token),
            json={"email_notifications": False},
        )
        assert resp.status_code == 200
        assert resp.json()["email_notifications"] is False

    async def test_change_password(self, client: AsyncClient, setup_db):
        token = await _setup_admin(client, setup_db)
        resp = await client.post(
            "/api/v1/admin/settings/change-password",
            headers=auth(token),
            json={
                "current_password": "password123",
                "new_password": "newpassword456",
            },
        )
        assert resp.status_code == 200

    async def test_change_password_wrong_current(
        self,
        client: AsyncClient,
        setup_db,
    ):
        token = await _setup_admin(client, setup_db)
        resp = await client.post(
            "/api/v1/admin/settings/change-password",
            headers=auth(token),
            json={
                "current_password": "wrongpass",
                "new_password": "newpassword456",
            },
        )
        assert resp.status_code == 400

    async def test_login_history(self, client: AsyncClient, setup_db):
        token = await _setup_admin(client, setup_db)
        resp = await client.get(
            "/api/v1/admin/settings/login-history",
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_backup(self, client: AsyncClient, setup_db):
        token = await _setup_admin(client, setup_db)
        resp = await client.post(
            "/api/v1/admin/settings/backup",
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"
