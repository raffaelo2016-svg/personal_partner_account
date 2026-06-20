"""Тесты пагинации сообщений чата — before cursor, limit, порядок."""

from datetime import datetime, timedelta

from httpx import AsyncClient

from app.models.chat import ChatMessage
from tests.chat.conftest import auth
from tests.conftest import async_session_test


async def _seed_messages(room_id: str, count: int, sender_type: str = "user") -> list[str]:
    """Вставляет count сообщений с интервалом 1 секунда. Возвращает список ID по возрастанию created_at."""
    ids = []
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    async with async_session_test() as session:
        for i in range(count):
            msg = ChatMessage(
                room_id=room_id,
                sender_type=sender_type,
                text=f"Msg {i + 1}",
                delivery_status="sent",
            )
            session.add(msg)
            await session.flush()
            # Устанавливаем created_at вручную для гарантии порядка
            msg.created_at = base_time + timedelta(seconds=i)
            await session.flush()
            ids.append(str(msg.id))
        await session.commit()
    return ids


class TestPartnerPagination:
    """Пагинация сообщений партнёрского чата."""

    async def test_default_limit_returns_latest(self, client: AsyncClient, partner_token):
        """Без before — возвращает последние сообщения."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 30)

        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 20},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) == 20
        # Должны быть последние 20 (Msg 11..Msg 30), отсортированные ASC
        assert msgs[0]["text"] == "Msg 11"
        assert msgs[-1]["text"] == "Msg 30"

    async def test_before_cursor_returns_older(self, client: AsyncClient, partner_token):
        """before=ID → сообщения старше указанного."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 30)

        # Первая страница — последние 10
        resp1 = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10},
            headers=auth(partner_token),
        )
        page1 = resp1.json()
        assert len(page1) == 10
        assert page1[-1]["text"] == "Msg 30"
        oldest_id = page1[0]["id"]

        # Вторая страница — before самого старого из первой
        resp2 = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10, "before": oldest_id},
            headers=auth(partner_token),
        )
        page2 = resp2.json()
        assert len(page2) == 10
        # Не должно быть пересечений
        page1_ids = {m["id"] for m in page1}
        page2_ids = {m["id"] for m in page2}
        assert page1_ids.isdisjoint(page2_ids), "Страницы не должны пересекаться"
        # page2 должна содержать более старые сообщения
        assert page2[-1]["text"] == "Msg 20"

    async def test_third_page(self, client: AsyncClient, partner_token):
        """Три страницы покрывают все 30 сообщений."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 30)

        all_texts = []

        # Page 1
        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10},
            headers=auth(partner_token),
        )
        page = resp.json()
        all_texts.extend(m["text"] for m in page)
        cursor = page[0]["id"]

        # Page 2
        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10, "before": cursor},
            headers=auth(partner_token),
        )
        page = resp.json()
        all_texts.extend(m["text"] for m in page)
        cursor = page[0]["id"]

        # Page 3
        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10, "before": cursor},
            headers=auth(partner_token),
        )
        page = resp.json()
        all_texts.extend(m["text"] for m in page)

        assert len(set(all_texts)) == 30

    async def test_before_last_page_returns_empty(self, client: AsyncClient, partner_token):
        """Когда больше нет сообщений — пустой массив."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 5)

        # Загружаем все 5
        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10},
            headers=auth(partner_token),
        )
        page = resp.json()
        assert len(page) == 5
        oldest_id = page[0]["id"]

        # before самого старого — пусто
        resp2 = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10, "before": oldest_id},
            headers=auth(partner_token),
        )
        assert resp2.json() == []

    async def test_messages_sorted_asc(self, client: AsyncClient, partner_token):
        """Сообщения отсортированы по created_at ASC."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 10)

        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10},
            headers=auth(partner_token),
        )
        msgs = resp.json()
        timestamps = [m["created_at"] for m in msgs]
        assert timestamps == sorted(timestamps)

    async def test_before_invalid_id_returns_all(self, client: AsyncClient, partner_token):
        """before с несуществующим ID — игнорирует cursor, возвращает последние."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 5)

        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 10, "before": "00000000-0000-0000-0000-000000000000"},
            headers=auth(partner_token),
        )
        assert len(resp.json()) == 5

    async def test_limit_one(self, client: AsyncClient, partner_token):
        """limit=1 возвращает только последнее сообщение."""
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        await _seed_messages(room_id, 5)

        resp = await client.get(
            f"/api/v1/chat/rooms/{room_id}/messages",
            params={"limit": 1},
            headers=auth(partner_token),
        )
        msgs = resp.json()
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Msg 5"


class TestAdminPagination:
    """Пагинация сообщений админского чата."""

    async def _get_admin_room(self, client, admin_token, partner_with_rooms):
        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        return rooms[0]["id"]

    async def test_default_limit(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        await _seed_messages(room_id, 25)

        resp = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            params={
                "limit": 20,
            },
            headers=auth(admin_token),
        )
        msgs = resp.json()
        assert len(msgs) == 20
        assert msgs[-1]["text"] == "Msg 25"

    async def test_before_cursor(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        await _seed_messages(room_id, 25)

        resp1 = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            params={
                "limit": 10,
            },
            headers=auth(admin_token),
        )
        page1 = resp1.json()
        oldest_id = page1[0]["id"]

        resp2 = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            params={
                "limit": 10,
                "before": oldest_id,
            },
            headers=auth(admin_token),
        )
        page2 = resp2.json()
        assert len(page2) == 10

        page1_ids = {m["id"] for m in page1}
        page2_ids = {m["id"] for m in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_empty_after_all_loaded(self, client: AsyncClient, admin_token, partner_with_rooms):
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        await _seed_messages(room_id, 3)

        resp = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            params={
                "limit": 10,
            },
            headers=auth(admin_token),
        )
        page = resp.json()
        oldest_id = page[0]["id"]

        resp2 = await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            params={
                "limit": 10,
                "before": oldest_id,
            },
            headers=auth(admin_token),
        )
        assert resp2.json() == []

    async def test_loading_marks_read(self, client: AsyncClient, admin_token, partner_with_rooms):
        """Загрузка сообщений помечает прочитанным."""
        room_id = await self._get_admin_room(client, admin_token, partner_with_rooms)
        await _seed_messages(room_id, 5, sender_type="user")

        await client.get(
            f"/api/v1/admin/chat/rooms/{room_id}/messages",
            params={"limit": 20},
            headers=auth(admin_token),
        )

        rooms = (await client.get("/api/v1/admin/chat/rooms", headers=auth(admin_token))).json()
        room = next(r for r in rooms if r["id"] == room_id)
        assert room["unread_count"] == 0
