"""Полные API-тесты: Уведомления."""

from httpx import AsyncClient

from app.models.notification import Notification
from tests.api_integration.conftest import auth
from tests.conftest import async_session_test


async def _seed_notification(user_id, title="Тест", is_read=False):
    async with async_session_test() as session:
        n = Notification(user_id=user_id, type="info", title=title, message="Msg", is_read=is_read)
        session.add(n)
        await session.commit()
        await session.refresh(n)
        return str(n.id)


class TestNotificationsList:
    async def test_empty(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/notifications", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_with_notifications(self, client: AsyncClient, partner_token, partner_user):
        await _seed_notification(str(partner_user.id))
        data = (await client.get("/api/v1/notifications", headers=auth(partner_token))).json()
        assert data["total"] >= 1

    async def test_filter_unread(self, client: AsyncClient, partner_token, partner_user):
        await _seed_notification(str(partner_user.id), is_read=False)
        await _seed_notification(str(partner_user.id), is_read=True)
        data = (
            await client.get("/api/v1/notifications", params={"is_read": "false"}, headers=auth(partner_token))
        ).json()
        assert all(not n["is_read"] for n in data["items"])

    async def test_pagination(self, client: AsyncClient, partner_token, partner_user):
        for i in range(3):
            await _seed_notification(str(partner_user.id), title=f"N{i}")
        data = (await client.get("/api/v1/notifications", params={"page_size": 2}, headers=auth(partner_token))).json()
        assert len(data["items"]) <= 2


class TestUnreadCount:
    async def test_zero(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/notifications/unread-count", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["count"] >= 0

    async def test_increments(self, client: AsyncClient, partner_token, partner_user):
        before = (await client.get("/api/v1/notifications/unread-count", headers=auth(partner_token))).json()["count"]
        await _seed_notification(str(partner_user.id))
        after = (await client.get("/api/v1/notifications/unread-count", headers=auth(partner_token))).json()["count"]
        assert after == before + 1


class TestMarkRead:
    async def test_mark_one(self, client: AsyncClient, partner_token, partner_user):
        nid = await _seed_notification(str(partner_user.id))
        resp = await client.put(f"/api/v1/notifications/{nid}/read", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    async def test_mark_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000/read", headers=auth(partner_token)
        )
        assert resp.status_code == 404

    async def test_mark_all(self, client: AsyncClient, partner_token, partner_user):
        await _seed_notification(str(partner_user.id))
        await _seed_notification(str(partner_user.id))
        resp = await client.put("/api/v1/notifications/read-all", headers=auth(partner_token))
        assert resp.status_code == 200
        count = (await client.get("/api/v1/notifications/unread-count", headers=auth(partner_token))).json()["count"]
        assert count == 0

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code in (401, 403)
