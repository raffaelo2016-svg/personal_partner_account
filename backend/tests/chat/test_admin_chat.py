"""Тесты админского чата — API endpoints."""

from httpx import AsyncClient

from tests.chat.conftest import auth


class TestAdminRooms:
    """GET /api/v1/admin/chat/rooms"""

    async def test_returns_admin_rooms(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Админ видит admin-комнату каждого партнёра."""
        # partner_with_rooms создаёт комнаты (включая admin) через ensure_rooms
        resp = await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))
        assert resp.status_code == 200
        rooms = resp.json()
        assert len(rooms) >= 1
        for room in rooms:
            assert room["type"] == "admin"
            assert "partner_name" in room

    async def test_search_by_company_name(
        self, client: AsyncClient, admin_token, partner_with_rooms, partner2_with_rooms
    ):
        """Поиск фильтрует по названию компании."""
        resp = await client.get(
            "/api/v1/admin/chat/rooms",
            params={"search": "Chat Co"},
            headers=auth(admin_token),
        )
        rooms = resp.json()
        assert len(rooms) == 1
        assert rooms[0]["partner_name"] == "Chat Co"

    async def test_search_no_match(self, client: AsyncClient, admin_token, partner_with_rooms):
        resp = await client.get(
            "/api/v1/admin/chat/rooms",
            params={"search": "несуществующая"},
            headers=auth(admin_token),
        )
        assert resp.json() == []

    async def test_rooms_sorted_unread_first(
        self, client: AsyncClient, admin_token, partner_with_rooms, partner2_with_rooms
    ):
        """Комнаты с непрочитанными — сверху."""
        # Партнёр 2 отправляет сообщение (через admin-комнату)
        admin_rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        # Отправим сообщение от партнёра 1 в его admin-комнату
        partner1_admin_room = next((r for r in admin_rooms if r["partner_name"] == "Chat Co"), None)
        if partner1_admin_room:
            # Партнёр отправляет через WS или REST (юзаем сервис напрямую)
            from app.models.chat import ChatMessage
            from tests.conftest import async_session_test

            async with async_session_test() as session:
                msg = ChatMessage(
                    room_id=partner1_admin_room["id"],
                    sender_id=None,
                    sender_type="user",
                    text="Непрочитанное",
                    delivery_status="sent",
                )
                session.add(msg)
                await session.commit()

            rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
            assert rooms[0]["unread_count"] > 0, "Первая комната должна иметь непрочитанные"

    async def test_non_admin_forbidden(self, client: AsyncClient, partner_with_rooms):
        """Партнёр не имеет доступа к admin/chat."""
        resp = await client.get("/api/v1/admin/chat/rooms", headers=auth(partner_with_rooms))
        assert resp.status_code == 403

    async def test_tech_support_conversation_is_separate(self, client: AsyncClient, admin_token, partner_with_rooms):
        partner_rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_with_rooms))).json()
        support_room = next(room for room in partner_rooms if room["type"] == "tech_support")
        admin_room = next(room for room in partner_rooms if room["type"] == "admin")

        sent = await client.post(
            f"/api/v1/chat/rooms/{support_room['id']}/messages",
            json={"text": "Не открывается раздел клиентов"},
            headers=auth(partner_with_rooms),
        )
        assert sent.status_code == 201

        support_list = await client.get(
            "/api/v1/admin/chat/rooms",
            params={"room_type": "tech_support"},
            headers=auth(admin_token),
        )
        assert support_list.status_code == 200
        assert any(room["id"] == support_room["id"] and room["unread_count"] == 1 for room in support_list.json())

        admin_list = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        assert any(room["id"] == admin_room["id"] and room["unread_count"] == 0 for room in admin_list)
        assert all(room["type"] == "admin" for room in admin_list)

        messages = await client.get(
            f"/api/v1/admin/chat/rooms/{support_room['id']}/messages",
            headers=auth(admin_token),
        )
        assert messages.status_code == 200
        assert messages.json()[-1]["text"] == "Не открывается раздел клиентов"

        reply = await client.post(
            f"/api/v1/admin/chat/rooms/{support_room['id']}/messages",
            json={"text": "Проверим доступ"},
            headers=auth(admin_token),
        )
        assert reply.status_code == 201
        assert reply.json()["sender_type"] == "admin"

        partner_unread = await client.get("/api/v1/chat/unread-count", headers=auth(partner_with_rooms))
        assert partner_unread.json()["unread_count"] == 1
        partner_messages = await client.get(
            f"/api/v1/chat/rooms/{support_room['id']}/messages",
            headers=auth(partner_with_rooms),
        )
        assert partner_messages.json()[-1]["text"] == "Проверим доступ"
        final_unread = await client.get("/api/v1/chat/unread-count", headers=auth(partner_with_rooms))
        assert final_unread.json()["unread_count"] == 0


class TestAdminMessages:
    """GET/POST /api/v1/admin/chat/rooms/{room_id}/messages"""

    async def _get_admin_room(self, client, admin_token, partner_with_rooms):
        """Хелпер: получить admin-комнату первого партнёра."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        return rooms[0]["id"] if rooms else None

    async def test_send_admin_message(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        assert room_id

        resp = await client.post(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            json={"text": "Ответ от админа"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Ответ от админа"
        assert data["sender_type"] == "admin"

    async def test_loading_messages_marks_read(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Загрузка сообщений всегда помечает прочитанными."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)

        from app.models.chat import ChatMessage
        from tests.conftest import async_session_test

        async with async_session_test() as session:
            msg = ChatMessage(room_id=room_id, sender_type="user", text="Будет прочитано", delivery_status="sent")
            session.add(msg)
            await session.commit()

        await client.get(f"/api/v1/admin/chat/rooms/{room_id}/messages", headers=auth(admin_token))

        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room = next(r for r in rooms if r["id"] == room_id)
        assert room["unread_count"] == 0

    async def test_get_messages_with_mark_read(self, client: AsyncClient, admin_token, partner_with_rooms):
        """mark_read=true помечает user-сообщения прочитанными."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)

        from app.models.chat import ChatMessage
        from tests.conftest import async_session_test

        async with async_session_test() as session:
            msg = ChatMessage(
                room_id=room_id,
                sender_type="user",
                text="Будет прочитано",
                delivery_status="sent",
            )
            session.add(msg)
            await session.commit()

        # Загружаем с mark_read=true (дефолт)
        await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            headers=auth(admin_token),
        )

        # unread_count должен стать 0
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room = next(r for r in rooms if r["id"] == room_id)
        assert room["unread_count"] == 0


class TestAdminUnreadCount:
    """GET /api/v1/admin/chat/unread-count"""

    async def test_initial_unread_zero(self, client: AsyncClient, admin_token, partner_with_rooms):
        resp = await client.get("/api/v1/admin/chat/unread-count", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    async def test_unread_increases_with_user_message(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Новое user-сообщение увеличивает общий unread."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room_id = rooms[0]["id"]

        from app.models.chat import ChatMessage
        from tests.conftest import async_session_test

        async with async_session_test() as session:
            msg = ChatMessage(
                room_id=room_id,
                sender_type="user",
                text="Новое",
                delivery_status="sent",
            )
            session.add(msg)
            await session.commit()

        resp = await client.get("/api/v1/admin/chat/unread-count", headers=auth(admin_token))
        assert resp.json()["unread_count"] >= 1


class TestAdminDeleteMessage:
    """DELETE /api/v1/admin/chat/rooms/{room_id}/messages/{message_id}"""

    async def _get_admin_room(self, client, admin_token, partner_with_rooms):
        """Хелпер: получить admin-комнату первого партнёра."""
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        return rooms[0]["id"] if rooms else None

    async def _post_message(self, client, admin_token, room_id, text):
        resp = await client.post(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            json={"text": text},
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_admin_can_delete_message(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        assert room_id
        message_id = await self._post_message(client, admin_token, room_id, "Сообщение для удаления")

        resp = await client.delete(
            f"/api/v1/admin/chat/rooms/{room_id}/messages/{message_id}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 204

        msgs = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            headers=auth(admin_token),
        )
        assert all(m["id"] != message_id for m in msgs.json())

    async def test_delete_removes_for_partner_too(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        assert room_id
        message_id = await self._post_message(client, admin_token, room_id, "Увидит ли партнёр?")

        resp = await client.delete(
            f"/api/v1/admin/chat/rooms/{room_id}/messages/{message_id}",
            headers=auth(admin_token),
        )
        assert resp.status_code == 204

        partner_msgs = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            headers=auth(partner_with_rooms),
        )
        assert all(m["id"] != message_id for m in partner_msgs.json())

    async def test_partner_cannot_delete(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        assert room_id
        message_id = await self._post_message(client, admin_token, room_id, "Партнёр не сможет удалить")

        resp = await client.delete(
            f"/api/v1/admin/chat/rooms/{room_id}/messages/{message_id}",
            headers=auth(partner_with_rooms),
        )
        assert resp.status_code == 403

    async def test_delete_nonexistent_message_returns_404(
        self, client: AsyncClient, admin_token, partner_with_rooms
    ):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        assert room_id

        resp = await client.delete(
            f"/api/v1/admin/chat/rooms/{room_id}/messages/00000000-0000-0000-0000-000000000000",
            headers=auth(admin_token),
        )
        assert resp.status_code == 404
