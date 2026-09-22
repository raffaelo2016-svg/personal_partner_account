from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_partner(client: AsyncClient, setup_db):
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="chat_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        partner = Partner(
            user_id=user.id,
            company_name="Chat Co",
            director_name="Dir",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.commit()

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "chat_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestChat:
    async def test_list_rooms(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        resp = await client.get("/api/v1/chat/rooms", headers=auth(token))
        assert resp.status_code == 200
        rooms = resp.json()
        assert len(rooms) == 5
        types = {r["type"] for r in rooms}
        assert types == {"admin", "tech_support", "arbitration_manager", "assistant", "ai_assistant"}

    async def test_send_and_get_messages(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(token))).json()
        room_id = rooms[0]["id"]

        resp = await client.post(
            f"/api/v1/chat/rooms/{room_id}/messages",
            json={"text": "Привет!"},
            headers=auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["text"] == "Привет!"
        assert resp.json()["sender_type"] == "user"

        msgs = (
            await client.get(
                f"/api/v1/chat/rooms/{room_id}/messages",
                headers=auth(token),
            )
        ).json()
        assert len(msgs) >= 1

    async def test_ai_assistant_responds(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(token))).json()
        ai_room = next(r for r in rooms if r["type"] == "ai_assistant")

        resp = await client.post(
            f"/api/v1/chat/rooms/{ai_room['id']}/messages",
            json={"text": "Расскажи про документы"},
            headers=auth(token),
        )
        assert resp.status_code == 201

        msgs = (
            await client.get(
                f"/api/v1/chat/rooms/{ai_room['id']}/messages",
                headers=auth(token),
            )
        ).json()
        bot_msgs = [m for m in msgs if m["sender_type"] == "bot"]
        assert len(bot_msgs) >= 1
        assert "документ" in bot_msgs[0]["text"].lower()

    async def test_rooms_are_idempotent(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        r1 = (await client.get("/api/v1/chat/rooms", headers=auth(token))).json()
        r2 = (await client.get("/api/v1/chat/rooms", headers=auth(token))).json()
        assert {r["id"] for r in r1} == {r["id"] for r in r2}
