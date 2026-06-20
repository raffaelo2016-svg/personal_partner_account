from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_partner_with_client(client: AsyncClient, setup_db):
    from app.models.client import Client
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="status_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        partner = Partner(
            user_id=user.id,
            company_name="Test Co",
            director_name="Dir",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.flush()
        cl = Client(partner_id=partner.id, type="before_court", status="documents_collection", full_name="Test Client")
        session.add(cl)
        await session.commit()
        client_id = str(cl.id)

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "status_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token, client_id


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestStatusMachine:
    async def test_valid_transition(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        resp = await client.post(
            f"/api/v1/clients/{client_id}/status",
            json={"status": "documents_formation"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "documents_formation"

    async def test_invalid_transition(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        resp = await client.post(
            f"/api/v1/clients/{client_id}/status",
            json={"status": "realization"},
            headers=auth(token),
        )
        assert resp.status_code == 400

    async def test_chain_transitions(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        transitions = ["documents_formation", "sent_to_court", "documents_decision", "waiting_hearing"]
        for status in transitions:
            resp = await client.post(
                f"/api/v1/clients/{client_id}/status",
                json={"status": status},
                headers=auth(token),
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    async def test_status_history(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        await client.post(
            f"/api/v1/clients/{client_id}/status",
            json={"status": "documents_formation", "comment": "Starting docs"},
            headers=auth(token),
        )
        resp = await client.get(f"/api/v1/clients/{client_id}/status-history", headers=auth(token))
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) >= 1
        assert history[0]["from_status"] == "documents_collection"
        assert history[0]["to_status"] == "documents_formation"
        assert history[0]["comment"] == "Starting docs"

    async def test_transition_with_comment(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        resp = await client.post(
            f"/api/v1/clients/{client_id}/status",
            json={"status": "documents_formation", "comment": "Документы получены"},
            headers=auth(token),
        )
        assert resp.status_code == 200
