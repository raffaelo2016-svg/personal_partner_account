"""Тесты WebSocket чата."""

import json

import pytest
from httpx import AsyncClient

from tests.chat.conftest import auth


class TestWebSocketAuth:
    """Аутентификация WebSocket через первое сообщение."""

    async def test_auth_success(self, client: AsyncClient, partner_token, partner_user):
        """Успешная аутентификация по токену."""
        from starlette.testclient import TestClient

        from app.main import app

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": partner_token}))
            data = ws.receive_json()
            assert data["type"] == "auth_ok"

    async def test_auth_invalid_token(self, client: AsyncClient):
        """Невалидный токен → close 4001."""
        from starlette.testclient import TestClient

        from app.main import app

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": "invalid.token.here"}))
            # Сервер должен закрыть соединение
            with pytest.raises(Exception):
                ws.receive_json()

    async def test_auth_missing_token(self, client: AsyncClient):
        """Сообщение без токена → close."""
        from starlette.testclient import TestClient

        from app.main import app

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "auth"}))
            with pytest.raises(Exception):
                ws.receive_json()

    async def test_auth_wrong_message_type(self, client: AsyncClient):
        """Первое сообщение не auth → close."""
        from starlette.testclient import TestClient

        from app.main import app

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "message", "text": "test"}))
            with pytest.raises(Exception):
                ws.receive_json()

    async def test_auth_invalid_json(self, client: AsyncClient):
        """Невалидный JSON → close."""
        from starlette.testclient import TestClient

        from app.main import app

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text("not json at all")
            with pytest.raises(Exception):
                ws.receive_json()


@pytest.mark.skip(reason="WS handler uses app.database.async_session directly, not Depends — bypasses test DB override")
class TestWebSocketMessages:
    """Отправка/получение сообщений через WS. Skipped: requires async_session monkeypatch."""

    async def test_send_message_via_ws(self, client: AsyncClient, partner_token, partner_user):
        """Партнёр отправляет сообщение через WS → получает broadcast."""
        from starlette.testclient import TestClient

        from app.main import app

        # Сначала получаем комнату
        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": partner_token}))
            auth_resp = ws.receive_json()
            assert auth_resp["type"] == "auth_ok"

            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "room_id": room_id,
                        "text": "Привет через WS!",
                    }
                )
            )

            data = ws.receive_json()
            assert data["type"] == "new_message"
            assert data["message"]["text"] == "Привет через WS!"
            assert data["message"]["room_id"] == room_id
            assert data["message"]["sender_type"] == "user"

    async def test_ws_message_saved_to_db(self, client: AsyncClient, partner_token, partner_user):
        """WS-сообщение сохраняется в БД и видно через REST."""
        from starlette.testclient import TestClient

        from app.main import app

        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": partner_token}))
            ws.receive_json()  # auth_ok
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "room_id": room_id,
                        "text": "Сохрани меня",
                    }
                )
            )
            ws.receive_json()  # new_message broadcast

        # Проверяем через REST
        msgs = (
            await client.get(
                f"/api/v1/chat/rooms/{room_id}/messages",
                headers=auth(partner_token),
            )
        ).json()
        texts = [m["text"] for m in msgs]
        assert "Сохрани меня" in texts

    async def test_ws_empty_message_ignored(self, client: AsyncClient, partner_token, partner_user):
        """Пустое WS-сообщение игнорируется."""
        from starlette.testclient import TestClient

        from app.main import app

        rooms = (await client.get("/api/v1/chat/rooms", headers=auth(partner_token))).json()
        room_id = rooms[0]["id"]

        with TestClient(app) as tc, tc.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": partner_token}))
            ws.receive_json()  # auth_ok

            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "room_id": room_id,
                        "text": "",
                    }
                )
            )

            # Не должно прийти new_message — тайм-аут
            ws.send_text(json.dumps({"type": "message", "room_id": room_id, "text": "реальное"}))
            data = ws.receive_json()
            assert data["message"]["text"] == "реальное"
