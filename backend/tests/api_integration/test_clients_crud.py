"""Клиенты: CRUD, фильтрация, пагинация, progress."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestClientsCRUD:
    async def test_create_minimal(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients",
            json={"type": "before_court", "full_name": "Минимальный Клиент"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 201
        assert resp.json()["full_name"] == "Минимальный Клиент"

    async def test_create_missing_full_name(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients",
            json={"type": "before_court"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_delete_client(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.delete(f"/api/v1/clients/{c['id']}", headers=auth(partner_token))
        assert resp.status_code in (200, 204)

        resp2 = await client.get(f"/api/v1/clients/{c['id']}", headers=auth(partner_token))
        assert resp2.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.delete(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000",
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_get_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.get(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000",
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_update_partial(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token, full_name="Старое Имя")
        resp = await client.put(
            f"/api/v1/clients/{c['id']}",
            json={"full_name": "Новое Имя"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Новое Имя"


class TestClientsFiltering:
    async def test_filter_by_type(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, client_type="before_court", full_name="До суда")
        resp = await client.get(
            "/api/v1/clients",
            params={"type": "before_court"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(c["type"] == "before_court" for c in items)

    async def test_search_by_name(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Уникальноеимя Тест")
        resp = await client.get(
            "/api/v1/clients",
            params={"search": "Уникальноеимя"},
            headers=auth(partner_token),
        )
        items = resp.json()["items"]
        assert len(items) >= 1
        assert "Уникальноеимя" in items[0]["full_name"]

    async def test_pagination(self, client: AsyncClient, partner_token):
        for i in range(3):
            await create_client(client, partner_token, full_name=f"Клиент {i}")
        resp = await client.get(
            "/api/v1/clients",
            params={"page_size": 2, "page": 1},
            headers=auth(partner_token),
        )
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 3


class TestClientProgress:
    async def test_progress_endpoint(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.get(f"/api/v1/clients/{c['id']}/progress", headers=auth(partner_token))
        assert resp.status_code == 200


class TestClientStats:
    async def test_stats_counts(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Stat1")
        await create_client(client, partner_token, full_name="Stat2")
        resp = await client.get("/api/v1/clients/stats", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2
