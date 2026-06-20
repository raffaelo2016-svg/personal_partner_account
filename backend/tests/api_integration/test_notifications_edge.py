"""Notifications: edge cases."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth


class TestNotificationsEdgeCases:
    async def test_empty_list(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/notifications", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_unread_count_zero(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/notifications/unread-count", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["count"] >= 0

    async def test_mark_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000/read",
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_mark_all_read(self, client: AsyncClient, partner_token):
        resp = await client.put("/api/v1/notifications/read-all", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code in (401, 403)
