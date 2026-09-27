"""Admin dashboard: структура ответа, доступ, фильтры периода."""

from datetime import date, datetime, timedelta

from httpx import AsyncClient

from app.models.transaction import Transaction
from tests.api_integration.conftest import auth
from tests.conftest import async_session_test


class TestAdminDashboard:
    async def test_dashboard_structure(self, client: AsyncClient, admin_token, partner_token):
        resp = await client.get("/api/v1/admin/dashboard", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "main_stats" in data
        assert "movement_stats" in data
        assert "finance_stats" in data
        assert "comparison_stats" in data
        assert "risk_stats" in data
        assert "activity_trend" in data
        assert "top_partners" in data

    async def test_main_stats_fields(self, client: AsyncClient, admin_token, partner_token):
        resp = await client.get("/api/v1/admin/dashboard", headers=auth(admin_token))
        stats = resp.json()["main_stats"]
        for key in (
            "partners_count",
            "total_partners",
            "transmitting_partners",
            "activation_rate",
            "clients_per_active_partner",
        ):
            assert key in stats

    async def test_analytics_sections_have_expected_fields(self, client: AsyncClient, admin_token):
        data = (await client.get("/api/v1/admin/dashboard", headers=auth(admin_token))).json()
        assert len(data["activity_trend"]) == 6
        assert "collection_rate" in data["finance_stats"]
        assert "without_movement" in data["movement_stats"]
        assert "partners_without_first_client" in data["risk_stats"]

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/dashboard", headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/dashboard")
        assert resp.status_code in (401, 403)


class TestAdminDashboardPeriod:
    async def _add_txn(self, partner_id, created_at: datetime, amount: int = 10000) -> None:
        async with async_session_test() as session:
            txn = Transaction(
                partner_id=partner_id,
                amount=amount,
                status="completed",
                payment_method="yoo_money",
                created_at=created_at,
            )
            session.add(txn)
            await session.commit()

    async def test_range_filters_transactions(self, client: AsyncClient, admin_token, partner):
        today = date.today()
        old = datetime.combine(today - timedelta(days=10), datetime.min.time())
        recent = datetime.combine(today, datetime.min.time())
        await self._add_txn(partner.id, old)
        await self._add_txn(partner.id, recent)

        # today-only — только свежая транзакция
        resp = await client.get(
            f"/api/v1/admin/dashboard?date_from={today}&date_to={today}",
            headers=auth(admin_token),
        )
        data = resp.json()
        assert len(data["recent_transactions"]) == 1

        # широкий диапазон — обе
        resp_wide = await client.get(
            f"/api/v1/admin/dashboard?date_from={today - timedelta(days=30)}&date_to={today}",
            headers=auth(admin_token),
        )
        assert len(resp_wide.json()["recent_transactions"]) == 2

    async def test_partners_count_filtered_by_period(self, client: AsyncClient, admin_token, partner, partner2):
        # partner/partner2 только что созданы — сегодня. Диапазон из прошлого
        # даёт ноль партнёров.
        past = date.today() - timedelta(days=30)
        resp = await client.get(
            f"/api/v1/admin/dashboard?date_from={past - timedelta(days=1)}&date_to={past}",
            headers=auth(admin_token),
        )
        stats = resp.json()["main_stats"]
        assert stats["partners_count"] == 0
        assert stats["total_clients"] == 0

    async def test_top_partners_include_only_in_period(self, client: AsyncClient, admin_token, partner):
        past = date.today() - timedelta(days=30)
        resp = await client.get(
            f"/api/v1/admin/dashboard?date_from={past - timedelta(days=1)}&date_to={past}",
            headers=auth(admin_token),
        )
        # партнёр создан сегодня → не попадает в топ за прошлый период
        assert resp.json()["top_partners"] == []
