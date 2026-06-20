from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_user_with_notifications(client: AsyncClient, setup_db):
    from app.models.notification import Notification
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="notif_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        partner = Partner(
            user_id=user.id,
            company_name="Notif Co",
            director_name="Dir",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.flush()

        n1 = Notification(
            user_id=user.id,
            type="status_change",
            title="Статус",
            message="Клиент изменён",
            is_read=False,
        )
        n2 = Notification(user_id=user.id, type="new_task", title="Задача", message="Новая задача", is_read=False)
        n3 = Notification(user_id=user.id, type="overdue", title="Просрочка", message="Оплата просрочена", is_read=True)
        session.add_all([n1, n2, n3])
        await session.commit()
        notif_id = str(n1.id)

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "notif_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token, notif_id


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestNotifications:
    async def test_list_all(self, client: AsyncClient, setup_db):
        token, _ = await _setup_user_with_notifications(client, setup_db)
        resp = await client.get("/api/v1/notifications", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    async def test_list_unread(self, client: AsyncClient, setup_db):
        token, _ = await _setup_user_with_notifications(client, setup_db)
        resp = await client.get("/api/v1/notifications?is_read=false", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_unread_count(self, client: AsyncClient, setup_db):
        token, _ = await _setup_user_with_notifications(client, setup_db)
        resp = await client.get("/api/v1/notifications/unread-count", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    async def test_mark_read(self, client: AsyncClient, setup_db):
        token, notif_id = await _setup_user_with_notifications(client, setup_db)
        resp = await client.put(f"/api/v1/notifications/{notif_id}/read", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    async def test_mark_all_read(self, client: AsyncClient, setup_db):
        token, _ = await _setup_user_with_notifications(client, setup_db)
        resp = await client.put("/api/v1/notifications/read-all", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["marked_read"] == 2

        count_resp = await client.get("/api/v1/notifications/unread-count", headers=auth(token))
        assert count_resp.json()["count"] == 0
