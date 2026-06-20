"""Тесты broadcast: new_message и messages_read через REST endpoints."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.models.chat import ChatMessage
from tests.chat.conftest import auth
from tests.conftest import async_session_test


class TestBroadcastNewMessage:
    """POST /chat/rooms/{id}/messages → broadcast_new_message."""

    async def test_partner_post_broadcasts_to_others(self, client: AsyncClient, partner_token, partner_user):
        """Партнёр отправляет через REST → broadcast вызван с exclude."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        with patch("app.api.chat.broadcast_new_message", new_callable=AsyncMock) as mock_broadcast:
            resp = await client.post(
                f"/api/v1/chat/rooms/{room_id}/messages",
                json={"text": "Hello from REST"},
                headers=auth(partner_token),
            )
            assert resp.status_code == 201
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            msg_payload = call_args[0][0]
            assert msg_payload["text"] == "Hello from REST"
            assert msg_payload["sender_type"] == "user"
            # exclude_user_id передан
            assert call_args[1]["exclude_user_id"] is not None

    async def test_partner_post_excludes_sender(self, client: AsyncClient, partner_token, partner_user):
        """Отправитель исключён из broadcast."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        with patch("app.api.chat.broadcast_new_message", new_callable=AsyncMock) as mock_broadcast:
            await client.post(
                f"/api/v1/chat/rooms/{room_id}/messages",
                json={"text": "Test"},
                headers=auth(partner_token),
            )
            exclude_id = mock_broadcast.call_args[1]["exclude_user_id"]
            assert exclude_id == str(partner_user[0].id)

    async def test_admin_post_broadcasts(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Админ отправляет → broadcast вызван."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = rooms[0]["id"]

        with patch("app.api.admin_chat.broadcast_new_message", new_callable=AsyncMock) as mock_broadcast:
            resp = await client.post(
                f"/api/v1/admin/chat/rooms/{room_id}/messages",
                json={"text": "Admin reply"},
                headers=auth(admin_token),
            )
            assert resp.status_code == 201
            mock_broadcast.assert_called_once()
            msg_payload = mock_broadcast.call_args[0][0]
            assert msg_payload["text"] == "Admin reply"
            assert msg_payload["sender_type"] == "admin"

    async def test_admin_post_excludes_admin(self, client: AsyncClient, admin_token, admin_user, partner_with_rooms):
        """Админ исключён из собственного broadcast."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = rooms[0]["id"]

        with patch("app.api.admin_chat.broadcast_new_message", new_callable=AsyncMock) as mock_broadcast:
            await client.post(
                f"/api/v1/admin/chat/rooms/{room_id}/messages",
                json={"text": "Test"},
                headers=auth(admin_token),
            )
            exclude_id = mock_broadcast.call_args[1]["exclude_user_id"]
            assert exclude_id == str(admin_user.id)

    async def test_ai_response_broadcasts_to_all(self, client: AsyncClient, partner_token):
        """AI-ответ бродкастится всем (без exclude) чтобы отправитель тоже увидел."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        ai_room = next(r for r in rooms if r["type"] == "ai_assistant")

        with patch("app.api.chat.broadcast_new_message", new_callable=AsyncMock) as mock_broadcast:
            await client.post(
                f"/api/v1/chat/rooms/{ai_room['id']}/messages",
                json={"text": "вопрос про документы"},
                headers=auth(partner_token),
            )
            # Два вызова: 1) user message (exclude sender), 2) bot message (no exclude)
            assert mock_broadcast.call_count == 2
            # Второй вызов — bot, без exclude
            bot_call = mock_broadcast.call_args_list[1]
            assert bot_call[0][0]["sender_type"] == "bot"
            assert "exclude_user_id" not in bot_call[1] or bot_call[1].get("exclude_user_id") is None


class TestBroadcastMessagesRead:
    """GET messages с mark_read → broadcast_messages_read."""

    async def test_mark_read_broadcasts(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Админ загружает сообщения с mark_read=true → broadcast."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = rooms[0]["id"]

        # Вставляем непрочитанное сообщение
        async with async_session_test() as session:
            msg = ChatMessage(room_id=room_id, sender_type="user", text="Unread", delivery_status="sent")
            session.add(msg)
            await session.commit()

        with patch("app.api.admin_chat.broadcast_messages_read", new_callable=AsyncMock) as mock_broadcast:
            await client.get(
                f"/api/v1/admin/chat/rooms/{room_id}/messages",
                params={},
                headers=auth(admin_token),
            )
            mock_broadcast.assert_called_once()
            assert mock_broadcast.call_args[0][0] == room_id

    async def test_no_broadcast_when_nothing_to_mark(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Нет непрочитанных → broadcast НЕ вызван (count=0)."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = rooms[0]["id"]

        with patch("app.api.admin_chat.broadcast_messages_read", new_callable=AsyncMock) as mock_broadcast:
            await client.get(
                f"/api/v1/admin/chat/rooms/{room_id}/messages",
                headers=auth(admin_token),
            )
            mock_broadcast.assert_not_called()

    async def test_partner_read_broadcasts(self, client: AsyncClient, partner_token, admin_token, partner_with_rooms):
        """Партнёр загружает сообщения → broadcast для admin-сообщений."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = rooms[0]["id"]

        # Вставляем admin-сообщение
        async with async_session_test() as session:
            msg = ChatMessage(room_id=room_id, sender_type="admin", text="From admin", delivery_status="sent")
            session.add(msg)
            await session.commit()

        with patch("app.api.chat.broadcast_messages_read", new_callable=AsyncMock) as mock_broadcast:
            await client.get(
                f"/api/v1/chat/rooms/{room_id}/messages",
                headers=auth(partner_with_rooms),
            )
            mock_broadcast.assert_called_once()


class TestBroadcastPayloadFormat:
    """Формат payload broadcast-сообщений."""

    async def test_new_message_payload_has_required_fields(self, client: AsyncClient, partner_token):
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        with patch("app.api.chat.broadcast_new_message", new_callable=AsyncMock) as mock_broadcast:
            await client.post(
                f"/api/v1/chat/rooms/{room_id}/messages",
                json={"text": "Check fields"},
                headers=auth(partner_token),
            )
            payload = mock_broadcast.call_args[0][0]
            assert "id" in payload
            assert "room_id" in payload
            assert "sender_id" in payload
            assert "sender_type" in payload
            assert "text" in payload
            assert "created_at" in payload
            assert payload["room_id"] == room_id
