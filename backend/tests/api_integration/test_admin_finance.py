"""Admin finance: список всех транзакций с пагинацией и фильтрами."""

from httpx import AsyncClient

from app.models.transaction import Transaction
from tests.api_integration.conftest import auth, create_client
from tests.conftest import async_session_test


async def _seed_transactions(partner_id: str, statuses: list[str]) -> None:
    async with async_session_test() as session:
        for idx, status in enumerate(statuses):
            session.add(
                Transaction(
                    partner_id=partner_id,
                    amount=(idx + 1) * 10000,
                    status=status,
                    payment_method="yoo_money",
                    external_id=f"ext-{idx}",
                )
            )
        await session.commit()


class TestAdminTransactions:
    async def test_forbidden_for_partner(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/finance/transactions", headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/finance/transactions")
        assert resp.status_code in (401, 403)

    async def test_empty_list(self, client: AsyncClient, admin_token):
        resp = await client.get("/api/v1/admin/finance/transactions", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"items": [], "total": 0, "page": 1, "pages": 0, "page_size": 20}

    async def test_pagination(self, client: AsyncClient, admin_token, partner, partner_token):
        await create_client(client, partner_token)
        await _seed_transactions(str(partner.id), ["completed"] * 25)

        r1 = await client.get(
            "/api/v1/admin/finance/transactions?page=1&page_size=10",
            headers=auth(admin_token),
        )
        assert r1.status_code == 200
        page1 = r1.json()
        assert page1["total"] == 25
        assert page1["pages"] == 3
        assert page1["page"] == 1
        assert len(page1["items"]) == 10

        r2 = await client.get(
            "/api/v1/admin/finance/transactions?page=3&page_size=10",
            headers=auth(admin_token),
        )
        page3 = r2.json()
        assert len(page3["items"]) == 5

    async def test_filter_by_status(self, client: AsyncClient, admin_token, partner):
        await _seed_transactions(str(partner.id), ["pending", "pending", "completed", "failed"])

        resp = await client.get(
            "/api/v1/admin/finance/transactions?status=pending",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(item["status"] == "pending" for item in data["items"])

    async def test_item_shape(self, client: AsyncClient, admin_token, partner):
        await _seed_transactions(str(partner.id), ["completed"])

        resp = await client.get("/api/v1/admin/finance/transactions", headers=auth(admin_token))
        item = resp.json()["items"][0]
        assert set(item.keys()) == {
            "id",
            "partner_id",
            "partner_name",
            "client_name",
            "amount",
            "status",
            "payment_method",
            "external_id",
            "created_at",
        }
        assert item["partner_name"] == "Test Co"
        assert item["client_name"] is None  # нет связанного court_fee

    async def test_invalid_status_rejected(self, client: AsyncClient, admin_token):
        resp = await client.get(
            "/api/v1/admin/finance/transactions?status=bogus",
            headers=auth(admin_token),
        )
        assert resp.status_code == 422
