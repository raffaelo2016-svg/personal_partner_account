"""Полные API-тесты: Финансы — court-fees, summary, debt-banner, pay, history."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestCourtFees:
    async def test_list_empty(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/court-fees", headers=auth(partner_token))
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_list_after_client_creation(self, client: AsyncClient, partner_token):
        """Создание клиента автоматически создаёт court_fee."""
        await create_client(client, partner_token)
        data = (await client.get("/api/v1/finance/court-fees", headers=auth(partner_token))).json()
        assert data["total"] >= 1

    async def test_list_pagination(self, client: AsyncClient, partner_token):
        for _ in range(3):
            await create_client(client, partner_token)
        data = (
            await client.get("/api/v1/finance/court-fees", params={"page_size": 2}, headers=auth(partner_token))
        ).json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 3

    async def test_filter_by_status(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token)
        resp = await client.get("/api/v1/finance/court-fees", params={"status": "unpaid"}, headers=auth(partner_token))
        assert resp.status_code == 200


class TestCourtFeeSummary:
    async def test_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/court-fees/summary", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        for key in ("total_debt", "current_debt", "overdue_debt", "unpaid_count"):
            assert key in data

    async def test_with_fee(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token)
        data = (await client.get("/api/v1/finance/court-fees/summary", headers=auth(partner_token))).json()
        assert data["unpaid_count"] >= 1


class TestDebtBanner:
    async def test_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/debt-banner", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_debt" in data
        assert "has_debt" in data


class TestPayment:
    async def test_pay_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/finance/pay",
            json={
                "court_fee_id": "00000000-0000-0000-0000-000000000000",
                "payment_method": "card",
            },
            headers=auth(partner_token),
        )
        assert resp.status_code in (400, 404)

    async def test_pay_existing(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token)
        fees = (await client.get("/api/v1/finance/court-fees", headers=auth(partner_token))).json()["items"]
        if fees:
            resp = await client.post(
                "/api/v1/finance/pay",
                json={
                    "court_fee_id": fees[0]["id"],
                    "payment_method": "card",
                },
                headers=auth(partner_token),
            )
            assert resp.status_code in (200, 201)


class TestTransactionHistory:
    async def test_empty(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/history", headers=auth(partner_token))
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/finance/history")
        assert resp.status_code in (401, 403)
