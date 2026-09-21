"""Полные API-тесты: Финансы — court-fees, summary, debt-banner, pay, history."""

from datetime import date, timedelta

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client
from tests.conftest import async_session_test


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

    async def test_free_client_limit_is_used_before_paid_fees(
        self,
        client: AsyncClient,
        partner_token,
        partner,
    ):
        async with async_session_test() as session:
            saved_partner = await session.get(type(partner), partner.id)
            saved_partner.free_client_limit = 2
            saved_partner.promotion_start_date = date.today()
            saved_partner.promotion_end_date = date.today() + timedelta(days=30)
            await session.commit()

        for index in range(3):
            await create_client(client, partner_token, full_name=f"Льготный клиент {index}")

        fees = (await client.get("/api/v1/finance/court-fees", headers=auth(partner_token))).json()["items"]
        promo_fees = [fee for fee in fees if fee["status"] == "promo_free"]
        paid_fees = [fee for fee in fees if fee["status"] == "unpaid"]

        assert len(promo_fees) == 2
        assert all(fee["amount"] == 0 for fee in promo_fees)
        assert all(fee["discount_amount"] == fee["base_amount"] for fee in promo_fees)
        assert len(paid_fees) == 1

        summary = (await client.get("/api/v1/finance/court-fees/summary", headers=auth(partner_token))).json()
        assert summary["free_client_limit"] == 2
        assert summary["free_clients_used"] == 2
        assert summary["free_clients_remaining"] == 0
        assert summary["promotion_active"] is False

    async def test_expired_promotion_does_not_make_client_free(
        self,
        client: AsyncClient,
        partner_token,
        partner,
    ):
        async with async_session_test() as session:
            saved_partner = await session.get(type(partner), partner.id)
            saved_partner.free_client_limit = 10
            saved_partner.promotion_start_date = date.today() - timedelta(days=60)
            saved_partner.promotion_end_date = date.today() - timedelta(days=30)
            await session.commit()

        await create_client(client, partner_token, full_name="Клиент после акции")
        fees = (await client.get("/api/v1/finance/court-fees", headers=auth(partner_token))).json()["items"]

        assert fees[0]["status"] == "unpaid"
        assert fees[0]["amount"] == fees[0]["base_amount"]


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
