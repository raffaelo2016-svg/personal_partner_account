"""Полные API-тесты: Задачи — CRUD, фильтры, stats, urgent, isolation, validation."""

from datetime import date, timedelta

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client, create_task


class TestTaskCreate:
    async def test_create_success(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"], title="Новая задача")
        assert t["title"] == "Новая задача"
        assert t["status"] == "pending"
        assert t["priority"] == "medium"

    async def test_create_with_priority(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"], priority="high")
        assert t["priority"] == "high"

    async def test_create_general_task_for_authenticated_partner(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "title": "X",
                "assigned_to": "uritech",
                "due_date": str(date.today() + timedelta(days=1)),
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 201
        assert resp.json()["client_id"] is None

    async def test_create_missing_title(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "client_id": c["id"],
                "due_date": str(date.today()),
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_create_empty_title(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "client_id": c["id"],
                "title": "",
                "due_date": str(date.today()),
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_create_title_max_length(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "client_id": c["id"],
                "title": "А" * 255,
                "assigned_to": "uritech",
                "due_date": str(date.today()),
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 201

    async def test_create_title_over_max(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "client_id": c["id"],
                "title": "А" * 256,
                "due_date": str(date.today()),
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 422


class TestTaskUpdate:
    async def test_update_title(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.put(f"/api/v1/tasks/{t['id']}", json={"title": "Обновлено"}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["title"] == "Обновлено"

    async def test_update_status_to_completed(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.put(f"/api/v1/tasks/{t['id']}", json={"status": "completed"}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    async def test_update_priority(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.put(f"/api/v1/tasks/{t['id']}", json={"priority": "high"}, headers=auth(partner_token))
        assert resp.json()["priority"] == "high"

    async def test_update_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000", json={"title": "X"}, headers=auth(partner_token)
        )
        assert resp.status_code == 404

    async def test_update_empty_body(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"], title="Original")
        resp = await client.put(f"/api/v1/tasks/{t['id']}", json={}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["title"] == "Original"


class TestTaskDelete:
    async def test_delete(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.delete(f"/api/v1/tasks/{t['id']}", headers=auth(partner_token))
        assert resp.status_code == 204

    async def test_delete_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.delete("/api/v1/tasks/00000000-0000-0000-0000-000000000000", headers=auth(partner_token))
        assert resp.status_code == 404


class TestTaskFilters:
    async def test_filter_by_priority(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        await create_task(client, partner_token, c["id"], priority="high", title="H")
        await create_task(client, partner_token, c["id"], priority="low", title="L")
        items = (await client.get("/api/v1/tasks", params={"priority": "high"}, headers=auth(partner_token))).json()[
            "items"
        ]
        assert all(t["priority"] == "high" for t in items)

    async def test_filter_by_client_id(self, client: AsyncClient, partner_token):
        c1 = await create_client(client, partner_token, full_name="C1")
        c2 = await create_client(client, partner_token, full_name="C2")
        await create_task(client, partner_token, c1["id"], title="T1")
        await create_task(client, partner_token, c2["id"], title="T2")
        items = (await client.get("/api/v1/tasks", params={"client_id": c1["id"]}, headers=auth(partner_token))).json()[
            "items"
        ]
        assert all(t["client_id"] == c1["id"] for t in items)

    async def test_search_by_title(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        await create_task(client, partner_token, c["id"], title="УникальнаяЗадачаXYZ")
        items = (
            await client.get("/api/v1/tasks", params={"search": "УникальнаяЗадачаXYZ"}, headers=auth(partner_token))
        ).json()["items"]
        assert len(items) >= 1


class TestTaskStats:
    async def test_stats_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/tasks/stats", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        for key in ("total", "pending", "in_progress", "completed", "overdue", "completion_percent"):
            assert key in data

    async def test_stats_after_create(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        await create_task(client, partner_token, c["id"])
        data = (await client.get("/api/v1/tasks/stats", headers=auth(partner_token))).json()
        assert data["total"] >= 1
        assert data["pending"] >= 1


class TestTaskUrgent:
    async def test_urgent_returns_list(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/tasks/urgent", headers=auth(partner_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestTaskIsolation:
    async def test_partner_cannot_update_other(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.put(f"/api/v1/tasks/{t['id']}", json={"title": "Hack"}, headers=auth(partner_token2))
        assert resp.status_code in (403, 404)

    async def test_partner_cannot_delete_other(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        t = await create_task(client, partner_token, c["id"])
        resp = await client.delete(f"/api/v1/tasks/{t['id']}", headers=auth(partner_token2))
        assert resp.status_code in (403, 404)

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code in (401, 403)
