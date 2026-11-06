"""Admin partners: update, delete, фильтрация, поиск."""

from datetime import date

from httpx import AsyncClient

from tests.api_integration.conftest import auth
from tests.conftest import async_session_test


class TestAdminPartnersCRUD:
    async def test_get_partner_details(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(f"/api/v1/admin/partners/{partner.id}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Test Co"

    async def test_update_partner_status(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"status": "blocked"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

    async def test_update_partner_company_name(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"company_name": "Новое название"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Новое название"

    async def test_update_partner_region_sets_timezone(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"region": "Свердловская область"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "Свердловская область"
        assert body["timezone"] == "Asia/Yekaterinburg"

    async def test_update_partner_rejects_unknown_region(self, client: AsyncClient, admin_token, partner):
        resp = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"region": "Несуществующий регион"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_update_financial_terms_repairs_open_fee(self, client: AsyncClient, admin_token, partner):
        from app.models.client import Client
        from app.models.court_fee import CourtFee

        async with async_session_test() as session:
            debtor = Client(
                partner_id=partner.id,
                type="in_court",
                status="realization",
                full_name="Долматов Евгений Николаевич",
                court_procedure_date=date(2026, 5, 14),
            )
            session.add(debtor)
            await session.flush()
            fee = CourtFee(
                client_id=debtor.id,
                partner_id=partner.id,
                base_amount=500_000,
                discount_amount=0,
                amount=500_000,
                status="unpaid",
                due_date=date(2026, 11, 10),
            )
            session.add(fee)
            await session.commit()
            fee_id = fee.id

        response = await client.put(
            f"/api/v1/admin/partners/{partner.id}",
            json={"court_fee_per_client": 1_700_000, "payment_term_days": 10},
            headers=auth(admin_token),
        )

        assert response.status_code == 200
        async with async_session_test() as session:
            updated_fee = await session.get(CourtFee, fee_id)
            assert updated_fee.base_amount == 1_700_000
            assert updated_fee.amount == 1_700_000
            assert updated_fee.due_date == date(2026, 5, 24)
            assert updated_fee.status == "overdue"

    async def test_delete_partner(self, client: AsyncClient, admin_token, partner):
        resp = await client.delete(f"/api/v1/admin/partners/{partner.id}", headers=auth(admin_token))
        assert resp.status_code == 204

    async def test_delete_nonexistent(self, client: AsyncClient, admin_token):
        resp = await client.delete(
            "/api/v1/admin/partners/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_partner_cannot_access(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/admin/partners", headers=auth(partner_token))
        assert resp.status_code == 403


class TestAdminPartnersFiltering:
    async def test_filter_by_status(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(
            "/api/v1/admin/partners",
            params={"status": "active"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(p["status"] == "active" for p in items)

    async def test_search_by_company(self, client: AsyncClient, admin_token, partner):
        resp = await client.get(
            "/api/v1/admin/partners",
            params={"search": "Test"},
            headers=auth(admin_token),
        )
        items = resp.json()["items"]
        assert len(items) >= 1

    async def test_pagination(self, client: AsyncClient, admin_token, partner, partner2):
        resp = await client.get(
            "/api/v1/admin/partners",
            params={"page_size": 1, "page": 1},
            headers=auth(admin_token),
        )
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] >= 2
