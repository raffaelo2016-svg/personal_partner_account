"""Tasks: delete, фильтрация, изоляция."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client, create_task


class TestTasksCRUD:
    async def test_delete_task(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.delete(f"/api/v1/tasks/{t['id']}", headers=auth(partner_token))
        assert resp.status_code == 204

    async def test_delete_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.delete(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000",
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_create_without_required(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "No client"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422


class TestTasksFiltering:
    async def test_filter_by_priority(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        await create_task(client, partner_token, c["id"], priority="high", title="Высокий")
        await create_task(client, partner_token, c["id"], priority="low", title="Низкий")
        resp = await client.get(
            "/api/v1/tasks",
            params={"priority": "high"},
            headers=auth(partner_token),
        )
        items = resp.json()["items"]
        assert all(t["priority"] == "high" for t in items)

    async def test_filter_by_client_id(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        await create_task(client, partner_token, c["id"], title="Для клиента")
        resp = await client.get(
            "/api/v1/tasks",
            params={"client_id": c["id"]},
            headers=auth(partner_token),
        )
        items = resp.json()["items"]
        assert len(items) >= 1
        assert all(t["client_id"] == c["id"] for t in items)

    async def test_search_by_title(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        await create_task(client, partner_token, c["id"], title="УникальнаяЗадача")
        resp = await client.get(
            "/api/v1/tasks",
            params={"search": "УникальнаяЗадача"},
            headers=auth(partner_token),
        )
        items = resp.json()["items"]
        assert len(items) >= 1


class TestTasksIsolation:
    async def test_cannot_update_other_partner_task(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.put(
            f"/api/v1/tasks/{t['id']}",
            json={"title": "Hacked"},
            headers=auth(partner_token2),
        )
        assert resp.status_code in (403, 404)
