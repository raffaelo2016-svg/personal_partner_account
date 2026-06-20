"""Тесты партнёрского чата — API endpoints."""

from httpx import AsyncClient

from tests.chat.conftest import auth


class TestPartnerRooms:
    """GET /api/v1/chat/rooms"""

    async def test_returns_all_room_types(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/chat/rooms", headers=auth(partner_token))
        assert resp.status_code == 200
        rooms = resp.json()
        assert len(rooms) == 4
        types = {r["type"] for r in rooms}
        assert types == {"admin", "arbitration_manager", "assistant", "ai_assistant"}

    async def test_rooms_idempotent(self, client: AsyncClient, partner_token):
        """Повторный запрос не создаёт дубли."""
        r1 = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        r2 = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        assert {r["id"] for r in r1} == {r["id"] for r in r2}

    async def test_rooms_isolated_between_partners(self, client: AsyncClient, partner_token, partner_token2):
        """Партнёры видят только свои комнаты."""
        r1 = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        r2 = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token2))).json()
        ids1 = {r["id"] for r in r1}
        ids2 = {r["id"] for r in r2}
        assert ids1.isdisjoint(ids2), "Партнёры не должны видеть чужие комнаты"

    async def test_unread_count_initially_zero(self, client: AsyncClient, partner_token):
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        for room in rooms:
            assert room["unread_count"] == 0

    async def test_unauthenticated_returns_error(self, client: AsyncClient):
        resp = await client.get("/api/v1/chat/rooms")
        assert resp.status_code in (401, 403)


class TestPartnerMessages:
    """POST/GET /api/v1/chat/rooms/{room_id}/messages"""

    async def test_send_message(self, client: AsyncClient, partner_token):
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        resp = await client.post(
            f"/api/v1/chat/rooms/{room_id}/messages",
            json={"text": "Привет!"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Привет!"
        assert data["sender_type"] == "user"
        assert data["delivery_status"] == "sent"

    async def test_get_messages(self, client: AsyncClient, partner_token):
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await client.post(
            f"/api/v1/chat/rooms/{room_id}/messages",
            json={"text": "Msg 1"},
            headers=auth(partner_token),
        )
        await client.post(
            f"/api/v1/chat/rooms/{room_id}/messages",
            json={"text": "Msg 2"},
            headers=auth(partner_token),
        )

        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) >= 2
        # Сообщения отсортированы по created_at ASC
        assert msgs[-2]["text"] == "Msg 1"
        assert msgs[-1]["text"] == "Msg 2"

    async def test_messages_pagination_limit(self, client: AsyncClient, partner_token):
        """Параметр limit ограничивает кол-во сообщений."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        for i in range(5):
            await client.post(
                f"/api/v1/chat/rooms/{room_id}/messages",
                json={"text": f"Msg {i}"},
                headers=auth(partner_token),
            )

        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 2},
            headers=auth(partner_token),
        )
        assert len(resp.json()) == 2

    async def test_send_to_nonexistent_room_returns_404(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/chat/rooms/00000000-0000-0000-0000-000000000000/messages",
            json={"text": "test"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_send_empty_message_rejected(self, client: AsyncClient, partner_token):
        """Пустой текст → 422."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        resp = await client.post(
            f"/api/v1/chat/rooms/{room_id}/messages",
            json={"text": ""},
            headers=auth(partner_token),
        )
        assert resp.status_code == 422

    async def test_cannot_access_other_partners_room(self, client: AsyncClient, partner_token, partner_token2):
        """Партнёр не может отправить/прочитать сообщение в чужой комнате."""
        rooms1 = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id_1 = rooms1[0]["id"]

        resp = await client.post(
            f"/api/v1/chat/rooms/{room_id_1}/messages",
            json={"text": "Вторжение!"},
            headers=auth(partner_token2),
        )
        assert resp.status_code in (403, 404)

    async def test_ai_assistant_auto_reply(self, client: AsyncClient, partner_token):
        """AI-ассистент отвечает автоматически."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        ai_room = next(r for r in rooms if r["type"] == "ai_assistant")

        await client.post(
            f"/api/v1/chat/rooms/{ai_room['id']}/messages",
            json={"text": "Расскажи про документы"},
            headers=auth(partner_token),
        )

        msgs = (
            await client.get(
                f"/api/v1/chat/rooms/{ai_room['id']}/messages",
                headers=auth(partner_token),
            )
        ).json()

        bot_msgs = [m for m in msgs if m["sender_type"] == "bot"]
        assert len(bot_msgs) >= 1


class TestPartnerUnreadCount:
    """GET /api/v1/chat/unread-count"""

    async def test_initial_unread_zero(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/chat/unread-count", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0
