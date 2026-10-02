import asyncio
import contextlib
import html
import json
import time
from collections import defaultdict, deque

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.database import async_session

logger = structlog.get_logger()

router = APIRouter()

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 10
AUTH_TIMEOUT_SECONDS = 5
WS_MESSAGE_RATE_LIMIT = 20  # max messages per window
WS_RATE_WINDOW_SECONDS = 10
WS_MAX_MESSAGE_BYTES = 64 * 1024  # 64 KB payload limit


class ConnectionManager:
    """Менеджер WS-соединений: подключение, отключение, broadcast, heartbeat."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    def connect(self, user_id: str, ws: WebSocket) -> None:
        self._connections[user_id].append(ws)

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns and user_id in self._connections:
            del self._connections[user_id]

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    @property
    def online_user_ids(self) -> set[str]:
        return set(self._connections.keys())

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        for conn in self._connections.get(user_id, []):
            with contextlib.suppress(Exception):
                await conn.send_json(payload)

    async def broadcast(self, payload: dict, *, exclude_user_id: str | None = None) -> None:
        for uid, connections in self._connections.items():
            if uid == exclude_user_id:
                continue
            for conn in connections:
                with contextlib.suppress(Exception):
                    await conn.send_json(payload)

    async def send_to_users(self, user_ids: set[str], payload: dict, *, exclude_user_id: str | None = None) -> None:
        """Отправить только конкретным пользователям."""
        for uid in user_ids:
            if uid == exclude_user_id:
                continue
            for conn in self._connections.get(uid, []):
                with contextlib.suppress(Exception):
                    await conn.send_json(payload)

    async def broadcast_new_message(
        self, message: dict, *, target_user_ids: set[str] | None = None, exclude_user_id: str | None = None
    ) -> None:
        payload = {"type": "new_message", "message": message}
        if target_user_ids:
            await self.send_to_users(target_user_ids, payload, exclude_user_id=exclude_user_id)
        else:
            await self.broadcast(payload, exclude_user_id=exclude_user_id)

    async def broadcast_messages_read(
        self, room_id: str, *, target_user_ids: set[str] | None = None, exclude_user_id: str | None = None
    ) -> None:
        payload = {"type": "messages_read", "room_id": room_id}
        if target_user_ids:
            await self.send_to_users(target_user_ids, payload, exclude_user_id=exclude_user_id)
        else:
            await self.broadcast(payload, exclude_user_id=exclude_user_id)

    async def broadcast_status_update(
        self,
        message_ids: list[str],
        status: str,
        *,
        target_user_ids: set[str] | None = None,
        exclude_user_id: str | None = None,
    ) -> None:
        payload = {"type": "status_update", "message_ids": message_ids, "status": status}
        if target_user_ids:
            await self.send_to_users(target_user_ids, payload, exclude_user_id=exclude_user_id)
        else:
            await self.broadcast(payload, exclude_user_id=exclude_user_id)

    async def broadcast_message_deleted(
        self,
        room_id: str,
        message_id: str,
        *,
        target_user_ids: set[str] | None = None,
        exclude_user_id: str | None = None,
    ) -> None:
        payload = {"type": "message_deleted", "room_id": room_id, "message_id": message_id}
        if target_user_ids:
            await self.send_to_users(target_user_ids, payload, exclude_user_id=exclude_user_id)
        else:
            await self.broadcast(payload, exclude_user_id=exclude_user_id)


manager = ConnectionManager()


# ── Helpers: room participants ──


async def get_room_participant_ids(room_id: str) -> set[str]:
    """Получить user_ids участников комнаты (partner.user_id + все админы)."""
    from sqlalchemy import select

    from app.models.chat import ChatRoom
    from app.models.partner import Partner
    from app.models.user import User

    async with async_session() as session:
        room = await session.get(ChatRoom, room_id)
        if not room:
            return set()
        # Partner user_id
        partner = await session.get(Partner, room.partner_id)
        user_ids: set[str] = set()
        if partner:
            user_ids.add(str(partner.user_id))
        # All admin user_ids
        admins = await session.execute(select(User.id).where(User.role == "admin"))
        for row in admins:
            user_ids.add(str(row[0]))
    return user_ids


# ── Public helpers (imported by chat.py / admin_chat.py) ──


async def broadcast_new_message(
    message: dict, exclude_user_id: str | None = None, *, room_id: str | None = None
) -> None:
    targets = await get_room_participant_ids(room_id) if room_id else None
    await manager.broadcast_new_message(message, target_user_ids=targets, exclude_user_id=exclude_user_id)


async def broadcast_messages_read(room_id: str, exclude_user_id: str | None = None) -> None:
    targets = await get_room_participant_ids(room_id)
    await manager.broadcast_messages_read(room_id, target_user_ids=targets, exclude_user_id=exclude_user_id)


async def broadcast_status_update(
    message_ids: list[str], status: str, exclude_user_id: str | None = None, *, room_id: str | None = None
) -> None:
    targets = await get_room_participant_ids(room_id) if room_id else None
    await manager.broadcast_status_update(message_ids, status, target_user_ids=targets, exclude_user_id=exclude_user_id)


async def broadcast_message_deleted(room_id: str, message_id: str, exclude_user_id: str | None = None) -> None:
    targets = await get_room_participant_ids(room_id)
    await manager.broadcast_message_deleted(room_id, message_id, target_user_ids=targets, exclude_user_id=exclude_user_id)


# ── Auth ──


async def _authenticate(ws: WebSocket) -> str | None:
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketDisconnect):
        return None
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if msg.get("type") != "auth":
        return None
    token = msg.get("token")
    if not token or not isinstance(token, str):
        return None
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except Exception:
        return None


# ── Heartbeat ──


async def _heartbeat_loop(ws: WebSocket, user_id: str) -> None:
    """Шлёт ping каждые HEARTBEAT_INTERVAL секунд. При отсутствии pong — закрывает."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await asyncio.wait_for(ws.send_json({"type": "ping"}), timeout=HEARTBEAT_TIMEOUT)
            except Exception:
                logger.info("heartbeat_failed", user_id=user_id)
                with contextlib.suppress(Exception):
                    await ws.close(code=1001, reason="Heartbeat timeout")
                break
    except asyncio.CancelledError:
        pass


# ── WebSocket endpoint ──


@router.websocket("/api/v1/ws/chat")
async def websocket_chat(ws: WebSocket):
    from app.config import settings

    origin = ws.headers.get("origin")
    if origin and origin not in settings.cors_origins_list:
        await ws.close(code=4003, reason="Forbidden origin")
        return

    await ws.accept()
    user_id = await _authenticate(ws)
    if not user_id:
        with contextlib.suppress(Exception):
            await ws.close(code=4001, reason="Unauthorized")
        return

    with contextlib.suppress(Exception):
        await ws.send_json({"type": "auth_ok"})

    manager.connect(user_id, ws)
    logger.info("ws_connected", user_id=user_id)

    # Broadcast online status
    await manager.broadcast(
        {"type": "presence", "user_id": user_id, "status": "online"},
        exclude_user_id=user_id,
    )

    msg_timestamps: deque[float] = deque()

    try:
        while True:
            data = await ws.receive_text()

            # Size limit: drop huge payloads early
            if len(data) > WS_MAX_MESSAGE_BYTES:
                await ws.send_json({"type": "error", "message": "Payload too large"})
                continue

            # Rate limiting
            now = time.monotonic()
            msg_timestamps.append(now)
            while msg_timestamps and msg_timestamps[0] < now - WS_RATE_WINDOW_SECONDS:
                msg_timestamps.popleft()
            if len(msg_timestamps) > WS_MESSAGE_RATE_LIMIT:
                await ws.send_json({"type": "error", "message": "Rate limit exceeded"})
                continue

            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")
            room_id = msg.get("room_id")

            if msg_type == "pong":
                continue

            elif msg_type == "typing":
                await manager.broadcast(
                    {"type": "typing", "room_id": room_id, "user_id": user_id},
                    exclude_user_id=user_id,
                )

            elif msg_type == "message":
                text = msg.get("text", "")
                if not text or not room_id:
                    continue
                if len(text) > 5000:
                    await ws.send_json({"type": "error", "message": "Message too long"})
                    continue
                text = html.escape(text.strip(), quote=True)

                # Verify user has access to this room
                targets = await get_room_participant_ids(room_id)
                if user_id not in targets:
                    await ws.send_json({"type": "error", "message": "Access denied"})
                    continue

                async with async_session() as session:
                    from app.services.chat_service import get_ai_response, send_message

                    result = await send_message(session, room_id, user_id, "user", text)
                    broadcast_payload = {
                        "id": result.id,
                        "room_id": result.room_id,
                        "sender_id": result.sender_id,
                        "sender_type": result.sender_type,
                        "text": result.text,
                        "delivery_status": result.delivery_status,
                        "attachment_url": result.attachment_url,
                        "attachment_filename": result.attachment_filename,
                        "attachment_size": result.attachment_size,
                        "attachment_mime_type": result.attachment_mime_type,
                        "created_at": str(result.created_at),
                    }

                    from app.models.chat import ChatRoom

                    room = await session.get(ChatRoom, room_id)
                    ai_msg = None
                    if room and room.type == "ai_assistant":
                        ai_text = await get_ai_response(text)
                        ai_msg = await send_message(session, room_id, user_id, "bot", ai_text)

                    await session.commit()

                targets = await get_room_participant_ids(room_id)
                await manager.broadcast_new_message(broadcast_payload, target_user_ids=targets)
                if ai_msg:
                    await manager.broadcast_new_message(
                        {
                            "id": ai_msg.id,
                            "room_id": ai_msg.room_id,
                            "sender_id": ai_msg.sender_id,
                            "sender_type": ai_msg.sender_type,
                            "text": ai_msg.text,
                            "delivery_status": ai_msg.delivery_status,
                            "attachment_url": ai_msg.attachment_url,
                            "attachment_filename": ai_msg.attachment_filename,
                            "attachment_size": ai_msg.attachment_size,
                            "attachment_mime_type": ai_msg.attachment_mime_type,
                            "created_at": str(ai_msg.created_at),
                        },
                        target_user_ids=targets,
                    )

            elif msg_type == "delivered":
                message_ids = msg.get("message_ids", [])
                if message_ids:
                    async with async_session() as session:
                        from app.services.chat_service import mark_messages_delivered

                        count = await mark_messages_delivered(session, message_ids)
                        await session.commit()
                    if count:
                        targets = await get_room_participant_ids(room_id) if room_id else None
                        await manager.broadcast_status_update(
                            message_ids, "delivered", target_user_ids=targets, exclude_user_id=user_id
                        )

            elif msg_type == "read" and room_id:
                async with async_session() as session:
                    from app.services.chat_service import mark_messages_read

                    reader_role = msg.get("reader_role", "partner")
                    count = await mark_messages_read(session, room_id, reader_role=reader_role)
                    await session.commit()
                if count:
                    targets = await get_room_participant_ids(room_id)
                    await manager.broadcast_messages_read(room_id, target_user_ids=targets, exclude_user_id=user_id)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, ws)

        # Broadcast offline if no more connections
        if not manager.is_online(user_id):
            await manager.broadcast(
                {"type": "presence", "user_id": user_id, "status": "offline"},
            )

        logger.info("ws_disconnected", user_id=user_id)
