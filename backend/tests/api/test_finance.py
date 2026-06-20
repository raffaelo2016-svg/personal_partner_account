from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_partner_with_fee(client: AsyncClient, setup_db):
    from app.models.client import Client
    from app.models.court_fee import CourtFee
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="finance_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        partner = Partner(
            user_id=user.id,
            company_name="Finance Co",
            director_name="Dir",
            inn="7701234567",
            phone="+71234567890",
            status="active",
            court_fee_per_client=1_500_000,
            payment_term_days=10,
        )
        session.add(partner)
        await session.flush()

        cl = Client(
            partner_id=partner.id,
            type="in_court",
            status="sent_to_court",
            full_name="Debtor One",
            court_procedure_date=date.today() + timedelta(days=5),
        )
        session.add(cl)
        await session.flush()

        fee = CourtFee(
            client_id=cl.id,
            partner_id=partner.id,
            amount=1_500_000,
            status="unpaid",
            due_date=date.today() + timedelta(days=15),
        )
        session.add(fee)
        await session.commit()
        fee_id = str(fee.id)

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "finance_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token, fee_id


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestFinance:
    async def test_list_court_fees(self, client: AsyncClient, setup_db):
        token, _ = await _setup_partner_with_fee(client, setup_db)
        resp = await client.get("/api/v1/finance/court-fees", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_court_fees_summary(self, client: AsyncClient, setup_db):
        token, _ = await _setup_partner_with_fee(client, setup_db)
        resp = await client.get("/api/v1/finance/court-fees/summary", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["fee_per_client"] == 1_500_000
        assert data["total_debt"] >= 1_500_000

    async def test_debt_banner(self, client: AsyncClient, setup_db):
        token, _ = await _setup_partner_with_fee(client, setup_db)
        resp = await client.get("/api/v1/finance/debt-banner", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["has_debt"] is True

    async def test_pay_court_fee(self, client: AsyncClient, setup_db):
        token, fee_id = await _setup_partner_with_fee(client, setup_db)
        resp = await client.post(
            "/api/v1/finance/pay",
            json={"court_fee_id": fee_id, "payment_method": "card"},
            headers=auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "completed"
        assert resp.json()["amount"] == 1_500_000

    async def test_transaction_history(self, client: AsyncClient, setup_db):
        token, fee_id = await _setup_partner_with_fee(client, setup_db)
        await client.post(
            "/api/v1/finance/pay",
            json={"court_fee_id": fee_id},
            headers=auth(token),
        )
        resp = await client.get("/api/v1/finance/history", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
