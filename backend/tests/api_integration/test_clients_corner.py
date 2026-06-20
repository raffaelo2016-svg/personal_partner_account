"""Корнеры для /api/v1/clients: поиск с кириллицей/injection, границы длин, пагинация."""

from __future__ import annotations

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestSearchCorners:
    async def test_cyrillic_search_case_insensitive(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Иванов Пётр")
        await create_client(client, partner_token, full_name="Сидоров Иван")

        resp = await client.get("/api/v1/clients", params={"search": "пётр"}, headers=auth(partner_token))
        assert resp.status_code == 200
        names = [c["full_name"] for c in resp.json()["items"]]
        assert "Иванов Пётр" in names
        assert "Сидоров Иван" not in names

    async def test_sql_injection_payload_safe(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Иванов Иван")

        resp = await client.get(
            "/api/v1/clients",
            params={"search": "'; DROP TABLE clients; --"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        # Таблица жива — повторный запрос отдаёт созданного клиента
        resp2 = await client.get("/api/v1/clients", headers=auth(partner_token))
        assert resp2.status_code == 200
        assert resp2.json()["total"] >= 1

    async def test_search_too_long_rejected(self, client: AsyncClient, partner_token):
        """max_length=100 на query-параметре search."""
        resp = await client.get(
            "/api/v1/clients",
            params={"search": "a" * 101},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_search_whitespace_only(self, client: AsyncClient, partner_token):
        """Поиск с одними пробелами не должен крашить; поведение фиксируем."""
        await create_client(client, partner_token, full_name="Иванов Иван")
        resp = await client.get(
            "/api/v1/clients",
            params={"search": "   "},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200


class TestFullNameBoundaries:
    async def test_full_name_255_ok(self, client: AsyncClient, partner_token):
        name = "a" * 255
        resp = await client.post(
            "/api/v1/clients",
            json={"type": "before_court", "full_name": name, "phone": "+79001112233"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 201
        assert resp.json()["full_name"] == name

    async def test_full_name_256_rejected(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients",
            json={"type": "before_court", "full_name": "a" * 256, "phone": "+79001112233"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_full_name_empty_rejected(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients",
            json={"type": "before_court", "full_name": "", "phone": "+79001112233"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422


class TestPaginationBoundaries:
    async def test_page_size_zero_rejected(self, client: AsyncClient, partner_token):
        """PaginationParams: page_size >= 1 — 0 отбивается схемой."""
        resp = await client.get(
            "/api/v1/clients",
            params={"page_size": 0},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_page_size_over_max_rejected(self, client: AsyncClient, partner_token):
        """page_size <= 100 — 101 отбивается."""
        resp = await client.get(
            "/api/v1/clients",
            params={"page_size": 101},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_page_zero_rejected(self, client: AsyncClient, partner_token):
        resp = await client.get(
            "/api/v1/clients",
            params={"page": 0},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_empty_list_pages_zero(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/clients", headers=auth(partner_token))
        body = resp.json()
        assert body["total"] == 0
        assert body["pages"] == 0
        assert body["items"] == []

    async def test_page_size_larger_than_total(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="A")
        await create_client(client, partner_token, full_name="B")
        resp = await client.get(
            "/api/v1/clients",
            params={"page_size": 100},
            headers=auth(partner_token),
        )
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        assert body["pages"] == 1
