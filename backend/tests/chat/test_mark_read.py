"""Тесты mark_messages_read — корнер-кейсы пометки прочитанным."""

from httpx import AsyncClient

from app.models.chat import ChatMessage
from tests.chat.conftest import auth
from tests.conftest import async_session_test


async def _insert_message(room_id: str, sender_type: str, text: str, delivery_status: str = "sent"):
    """Хелпер: вставить сообщение напрямую в БД."""
    async with async_session_test() as session:
        msg = ChatMessage(
            room_id=room_id,
            sender_type=sender_type,
            text=text,
            delivery_status=delivery_status,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return str(msg.id)


class TestMarkReadLogic:
    """Корнер-кейсы mark_messages_read."""

    async def _get_admin_room(self, client, admin_token, partner_with_rooms):
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        return rooms[0]["id"]

    async def test_admin_marks_only_user_messages(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Админ помечает только user-сообщения, не свои."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)

        user_msg_id = await _insert_message(room_id, "user", "от партнёра")
        admin_msg_id = await _insert_message(room_id, "admin", "от админа")

        # Админ открывает комнату с mark_read=true
        await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            headers=auth(admin_token),
        )

        # Проверяем в БД
        async with async_session_test() as session:
            user_msg = await session.get(ChatMessage, user_msg_id)
            admin_msg = await session.get(ChatMessage, admin_msg_id)
            assert user_msg.delivery_status == "read", "user-сообщение должно быть помечено"
            assert admin_msg.delivery_status != "read", "admin-сообщение НЕ должно быть помечено"

    async def test_partner_marks_only_admin_messages(self, client: AsyncClient, partner_with_rooms, admin_token):
        """Партнёр помечает только admin-сообщения, не свои."""
        # Получаем admin-комнату через admin API
        admin_rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = admin_rooms[0]["id"]

        admin_msg_id = await _insert_message(room_id, "admin", "от админа")
        user_msg_id = await _insert_message(room_id, "user", "от партнёра")

        # Партнёр загружает admin-комнату через partner API
        # Партнёр видит только не-admin комнаты, но admin-комнату может загрузить по id
        await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            headers=auth(partner_with_rooms),
        )

        async with async_session_test() as session:
            admin_msg = await session.get(ChatMessage, admin_msg_id)
            user_msg = await session.get(ChatMessage, user_msg_id)
            assert admin_msg.delivery_status == "read", "admin-сообщение должно быть помечено"
            assert user_msg.delivery_status != "read", "user-сообщение НЕ должно быть помечено"

    async def test_already_read_not_affected(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Повторный mark_read не ломает уже прочитанные."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)

        await _insert_message(room_id, "user", "уже прочитано", delivery_status="read")
        await _insert_message(room_id, "user", "новое", delivery_status="sent")

        await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            headers=auth(admin_token),
        )

        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room = next(r for r in rooms if r["id"] == room_id)
        assert room["unread_count"] == 0

    async def test_empty_room_mark_read_noop(self, client: AsyncClient, admin_token, partner_with_rooms):
        """mark_read на пустой комнате не падает."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        resp = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200

    async def test_bot_messages_not_marked(self, client: AsyncClient, admin_token, partner_with_rooms):
        """bot-сообщения не помечаются ни админом, ни партнёром."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)

        bot_msg_id = await _insert_message(room_id, "bot", "Я бот")

        await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            headers=auth(admin_token),
        )

        async with async_session_test() as session:
            bot_msg = await session.get(ChatMessage, bot_msg_id)
            assert bot_msg.delivery_status != "read", "bot-сообщение не должно помечаться"
