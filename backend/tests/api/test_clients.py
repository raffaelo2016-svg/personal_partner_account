from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _create_partner_user_and_token(client: AsyncClient, setup_db, email="partner@test.com"):
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(email=email, hashed_password=hash_password("password123"), role="partner", is_active=True)
        session.add(user)
        await session.flush()
        partner = Partner(
            user_id=user.id,
            company_name="Test Co",
            director_name="Director",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.commit()
        partner_id = str(partner.id)

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
        return resp.json()["access_token"], partner_id


async def _get_admin_token(client: AsyncClient, setup_db):
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(email="admin@test.com", hashed_password=hash_password("admin123"), role="admin", is_active=True)
        session.add(user)
        await session.commit()

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "admin123"})
        return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


CLIENT_DATA = {
    "type": "before_court",
    "full_name": "Иванов Иван Иванович",
    "phone": "+79991234567",
    "region": "Москва",
}


class TestPartnerClients:
    async def test_create_client(self, client: AsyncClient, setup_db):
        token, _ = await _create_partner_user_and_token(client, setup_db)
        resp = await client.post("/api/v1/clients", json=CLIENT_DATA, headers=auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_name"] == "Иванов Иван Иванович"
        assert data["status"] in ("new", "documents_collection")

    async def test_list_clients(self, client: AsyncClient, setup_db):
        token, _ = await _create_partner_user_and_token(client, setup_db)
        await client.post("/api/v1/clients", json=CLIENT_DATA, headers=auth(token))
        resp = await client.get("/api/v1/clients", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_client(self, client: AsyncClient, setup_db):
        token, _ = await _create_partner_user_and_token(client, setup_db)
        create_resp = await client.post("/api/v1/clients", json=CLIENT_DATA, headers=auth(token))
        client_id = create_resp.json()["id"]
        resp = await client.get(f"/api/v1/clients/{client_id}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == client_id

    async def test_update_client(self, client: AsyncClient, setup_db):
        token, _ = await _create_partner_user_and_token(client, setup_db)
        create_resp = await client.post("/api/v1/clients", json=CLIENT_DATA, headers=auth(token))
        client_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/clients/{client_id}",
            json={"full_name": "Петров Пётр Петрович"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Петров Пётр Петрович"

    async def test_client_stats(self, client: AsyncClient, setup_db):
        token, _ = await _create_partner_user_and_token(client, setup_db)
        await client.post("/api/v1/clients", json=CLIENT_DATA, headers=auth(token))
        resp = await client.get("/api/v1/clients/stats", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_client_isolation(self, client: AsyncClient, setup_db):
        """Partner can only see own clients."""
        token1, _ = await _create_partner_user_and_token(client, setup_db, email="partner1@test.com")
        token2, _ = await _create_partner_user_and_token(client, setup_db, email="partner2@test.com")

        create_resp = await client.post("/api/v1/clients", json=CLIENT_DATA, headers=auth(token1))
        client_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/clients/{client_id}", headers=auth(token2))
        assert resp.status_code == 404


class TestAdminClients:
    async def test_admin_list_all_clients(self, client: AsyncClient, setup_db):
        admin_token = await _get_admin_token(client, setup_db)
        resp = await client.get("/api/v1/admin/clients", headers=auth(admin_token))
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_admin_forbidden_for_partner(self, client: AsyncClient, setup_db):
        token, _ = await _create_partner_user_and_token(client, setup_db)
        resp = await client.get("/api/v1/admin/clients", headers=auth(token))
        assert resp.status_code == 403
