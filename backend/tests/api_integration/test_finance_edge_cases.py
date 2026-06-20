"""Finance: edge cases."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth


class TestFinanceEdgeCases:
    async def test_court_fees_empty(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/court-fees", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_summary_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/court-fees/summary", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_debt_banner(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/debt-banner", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_history_empty(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/finance/history", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_pay_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/finance/pay",
            json={"court_fee_id": "00000000-0000-0000-0000-000000000000", "payment_method": "card"},
            headers=auth(partner_token),
        )
        assert resp.status_code in (400, 404)
