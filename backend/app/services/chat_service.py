import os

import structlog
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, FileTooLarge, Forbidden, NotFound, UnsupportedFileType
from app.models.chat import ChatMessage, ChatMessageEvent, ChatRoom
from app.schemas.chat import ChatMessageEventRead, ChatMessageRead, ChatRoomRead
from app.services.s3_service import delete_file_async, get_presigned_url, upload_file_async

logger = structlog.get_logger()

ROOM_TYPES = ["admin", "tech_support", "arbitration_manager", "assistant", "ai_assistant"]
STAFF_ROOM_TYPES = {"admin", "tech_support"}
CHAT_UPLOAD_MAX_SIZE_MB = 10
CHAT_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".zip"}
CHAT_ALLOWED_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _msg_to_read(m: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=str(m.id),
        room_id=str(m.room_id),
        sender_id=str(m.sender_id) if m.sender_id else None,
        sender_type=m.sender_type,
        text=m.text,
        delivery_status=m.delivery_status,
        bitrix_sync_status=m.bitrix_sync_status,
        bitrix_sync_error_code=m.bitrix_sync_error_code,
        bitrix_message_id=m.bitrix_message_id,
        attachment_url=get_presigned_url(m.attachment_s3_key) if m.attachment_s3_key else None,
        attachment_filename=m.attachment_filename,
        attachment_size=m.attachment_size,
        attachment_mime_type=m.attachment_mime_type,
        created_at=m.created_at,
        deleted_at=m.deleted_at,
    )


def _last_message_text(text: str | None, attachment_filename: str | None) -> str:
    if text:
        return text
    if attachment_filename:
        return f"Файл: {attachment_filename}"
    return "Файл"


async def upload_chat_file(file: UploadFile) -> tuple[str, str, int, str]:
    if not file.filename:
        raise BadRequest("No filename")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in CHAT_ALLOWED_EXTENSIONS:
        raise UnsupportedFileType()

    content_type = file.content_type or ""
    if ext == ".zip" and content_type in {"", "application/octet-stream", "application/x-zip-compressed"}:
        content_type = "application/zip"
    if content_type not in CHAT_ALLOWED_MIME_TYPES:
        raise UnsupportedFileType()

    data = await file.read()
    if len(data) > CHAT_UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        raise FileTooLarge()

    s3_key = await upload_file_async(data, file.filename, content_type)
    return s3_key, file.filename, len(data), content_type


async def ensure_rooms_for_partner(session: AsyncSession, partner_id: str) -> list[ChatRoom]:
    existing = await session.execute(select(ChatRoom).where(ChatRoom.partner_id == partner_id))
    rooms = list(existing.scalars().all())
    existing_types = {r.type for r in rooms}

    created = []
    for rt in ROOM_TYPES:
        if rt not in existing_types:
            room = ChatRoom(partner_id=partner_id, type=rt)
            session.add(room)
            rooms.append(room)
            created.append(rt)

    await session.flush()
    if created:
        logger.info("chat_rooms_created", partner_id=partner_id, types=created)
    return rooms


async def list_rooms(session: AsyncSession, partner_id: str) -> list[ChatRoomRead]:
    rooms = await ensure_rooms_for_partner(session, partner_id)
    room_ids = [room.id for room in rooms]

    # Один запрос: last_message per room
    last_msg_sub = (
        select(
            ChatMessage.room_id,
            ChatMessage.text,
            ChatMessage.attachment_filename,
            func.row_number()
            .over(
                partition_by=ChatMessage.room_id,
                order_by=ChatMessage.created_at.desc(),
            )
            .label("rn"),
        )
        .where(ChatMessage.room_id.in_(room_ids), ChatMessage.deleted_at.is_(None))
        .subquery()
    )
    last_msgs_q = select(last_msg_sub.c.room_id, last_msg_sub.c.text, last_msg_sub.c.attachment_filename).where(
        last_msg_sub.c.rn == 1
    )
    last_msgs = {
        str(r.room_id): _last_message_text(r.text, r.attachment_filename)
        for r in (await session.execute(last_msgs_q)).all()
    }

    # Один запрос: unread count per room
    unread_q = (
        select(ChatMessage.room_id, func.count().label("cnt"))
        .where(
            ChatMessage.room_id.in_(room_ids),
            ChatMessage.sender_type != "user",
            ChatMessage.delivery_status != "read",
            ChatMessage.deleted_at.is_(None),
        )
        .group_by(ChatMessage.room_id)
    )
    unreads = {str(r.room_id): r.cnt for r in (await session.execute(unread_q)).all()}

    return [
        ChatRoomRead(
            id=str(room.id),
            partner_id=str(room.partner_id),
            type=room.type,
            created_at=room.created_at,
            last_message=last_msgs.get(str(room.id)),
            unread_count=unreads.get(str(room.id), 0),
        )
        for room in rooms
    ]


async def get_messages(
    session: AsyncSession,
    room_id: str,
    partner_id: str,
    *,
    limit: int = 50,
    before: str | None = None,
) -> list[ChatMessageRead]:
    room = await session.get(ChatRoom, room_id)
    if not room:
        raise NotFound("Chat room not found")
    if str(room.partner_id) != partner_id:
        raise Forbidden("Access denied")

    q = select(ChatMessage).where(ChatMessage.room_id == room_id, ChatMessage.deleted_at.is_(None))
    if before:
        ref = await session.get(ChatMessage, before)
        if ref:
            q = q.where(ChatMessage.created_at < ref.created_at)

    q = q.order_by(ChatMessage.created_at.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [_msg_to_read(m) for m in reversed(rows)]


async def send_message(
    session: AsyncSession,
    room_id: str,
    sender_id: str,
    sender_type: str,
    text: str,
    *,
    partner_id: str | None = None,
    attachment_s3_key: str | None = None,
    attachment_filename: str | None = None,
    attachment_size: int | None = None,
    attachment_mime_type: str | None = None,
    sync_to_bitrix: bool = True,
) -> ChatMessageRead:
    room = await session.get(ChatRoom, room_id)
    if not room:
        raise NotFound("Chat room not found")
    if partner_id and str(room.partner_id) != partner_id:
        raise Forbidden("Access denied")
    if sender_type == "admin" and room.type not in STAFF_ROOM_TYPES:
        raise Forbidden("Access denied")

    msg = ChatMessage(
        room_id=room_id,
        sender_id=sender_id if sender_type != "bot" else None,
        sender_type=sender_type,
        text=text.strip() if text else "",
        attachment_s3_key=attachment_s3_key,
        attachment_filename=attachment_filename,
        attachment_size=attachment_size,
        attachment_mime_type=attachment_mime_type,
    )
    session.add(msg)
    await session.flush()

    if sync_to_bitrix and room.type == "admin" and sender_type in {"user", "admin"}:
        from app.integrations.bitrix24.chat import schedule_chat_message

        await schedule_chat_message(session, msg, room=room)
    await session.refresh(msg)

    try:
        logger.info("chat_message_sent", room_id=room_id, sender_type=sender_type)
        return _msg_to_read(msg)
    except Exception:
        if attachment_s3_key:
            await delete_file_async(attachment_s3_key)
        raise


async def delete_message(
    session: AsyncSession,
    room_id: str,
    message_id: str,
) -> tuple[str, str]:
    """Мягкое удаление сообщения администратором (видно всем участникам комнаты).

    Возвращает (room_id, message_id) для WS-рассылки. Повторное удаление — no-op.
    """
    from datetime import UTC, datetime

    room = await session.get(ChatRoom, room_id)
    if not room or room.type not in STAFF_ROOM_TYPES:
        raise NotFound("Admin chat room not found")

    msg = await session.get(ChatMessage, message_id)
    if not msg or str(msg.room_id) != room_id:
        raise NotFound("Message not found")

    if msg.deleted_at is None:
        msg.deleted_at = datetime.now(UTC)
        await session.flush()
        logger.info("chat_message_deleted", room_id=room_id, message_id=message_id, sender_type=msg.sender_type)

    return str(msg.room_id), str(msg.id)


async def list_admin_rooms(
    session: AsyncSession,
    *,
    search: str | None = None,
    room_type: str = "admin",
) -> list[ChatRoomRead]:
    """Чаты выбранного типа для панели администратора."""
    from datetime import UTC
    from datetime import datetime as dt

    from app.models.partner import Partner

    q = select(ChatRoom).where(ChatRoom.type == room_type)
    rooms = list((await session.execute(q)).scalars().all())

    partner_ids = {str(r.partner_id) for r in rooms}
    partners: dict[str, Partner] = {}
    if partner_ids:
        p_rows = (await session.execute(select(Partner).where(Partner.id.in_(partner_ids)))).scalars().all()
        partners = {str(p.id): p for p in p_rows}

    if search:
        pattern = search.lower()
        rooms = [
            r
            for r in rooms
            if pattern
            in (partners.get(str(r.partner_id), None) and partners[str(r.partner_id)].company_name or "").lower()
        ]

    room_ids = [room.id for room in rooms]

    # Один запрос: last_message + last_message_at per room
    last_msg_sub = (
        select(
            ChatMessage.room_id,
            ChatMessage.text,
            ChatMessage.attachment_filename,
            ChatMessage.created_at,
            func.row_number()
            .over(
                partition_by=ChatMessage.room_id,
                order_by=ChatMessage.created_at.desc(),
            )
            .label("rn"),
        )
        .where(ChatMessage.room_id.in_(room_ids), ChatMessage.deleted_at.is_(None))
        .subquery()
    )
    last_msgs_q = select(
        last_msg_sub.c.room_id,
        last_msg_sub.c.text,
        last_msg_sub.c.attachment_filename,
        last_msg_sub.c.created_at,
    ).where(last_msg_sub.c.rn == 1)
    last_msgs = {
        str(r.room_id): (_last_message_text(r.text, r.attachment_filename), r.created_at)
        for r in (await session.execute(last_msgs_q)).all()
    }

    # Один запрос: unread count per room
    unread_q = (
        select(ChatMessage.room_id, func.count().label("cnt"))
        .where(
            ChatMessage.room_id.in_(room_ids),
            ChatMessage.sender_type == "user",
            ChatMessage.delivery_status != "read",
            ChatMessage.deleted_at.is_(None),
        )
        .group_by(ChatMessage.room_id)
    )
    unreads = {str(r.room_id): r.cnt for r in (await session.execute(unread_q)).all()}

    result = []
    for room in rooms:
        rid = str(room.id)
        lm = last_msgs.get(rid)
        p = partners.get(str(room.partner_id))
        result.append(
            ChatRoomRead(
                id=rid,
                partner_id=str(room.partner_id),
                type=room.type,
                created_at=room.created_at,
                last_message=lm[0] if lm else None,
                last_message_at=lm[1] if lm else None,
                unread_count=unreads.get(rid, 0),
                partner_name=p.company_name if p else "Партнёр",
            )
        )

    # aware — ChatMessage.created_at теперь tz-aware (UTCDateTime), поэтому
    # запасной минимум тоже должен быть aware, иначе сортировка падает
    # TypeError: can't compare offset-naive and offset-aware datetimes.
    epoch = dt.min.replace(tzinfo=UTC)
    result.sort(key=lambda r: (r.unread_count > 0, r.last_message_at or epoch), reverse=True)
    return result


async def get_admin_messages(
    session: AsyncSession,
    room_id: str,
    *,
    limit: int = 50,
    before: str | None = None,
) -> list[ChatMessageRead]:
    room = await session.get(ChatRoom, room_id)
    if not room or room.type not in STAFF_ROOM_TYPES:
        raise NotFound("Admin chat room not found")

    q = select(ChatMessage).where(ChatMessage.room_id == room_id, ChatMessage.deleted_at.is_(None))
    if before:
        ref = await session.get(ChatMessage, before)
        if ref:
            q = q.where(ChatMessage.created_at < ref.created_at)

    q = q.order_by(ChatMessage.created_at.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [_msg_to_read(m) for m in reversed(rows)]


async def get_admin_message_events(
    session: AsyncSession,
    room_id: str,
    *,
    limit: int = 100,
) -> list[ChatMessageEventRead]:
    room = await session.get(ChatRoom, room_id)
    if not room or room.type != "admin":
        raise NotFound("Admin chat room not found")
    events = list(
        (
            await session.scalars(
                select(ChatMessageEvent)
                .where(ChatMessageEvent.room_id == room.id)
                .order_by(ChatMessageEvent.event_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [
        ChatMessageEventRead(
            id=str(event.id),
            room_id=str(event.room_id),
            chat_message_id=str(event.chat_message_id) if event.chat_message_id else None,
            bitrix_message_id=event.bitrix_message_id,
            event_type=event.event_type,
            actor_id=event.actor_id,
            event_at=event.event_at,
            created_at=event.created_at,
        )
        for event in events
    ]


async def mark_messages_read(
    session: AsyncSession,
    room_id: str,
    *,
    reader_role: str,
) -> int:
    """Отметить сообщения как прочитанные. admin читает user-сообщения, partner читает admin-сообщения."""
    sender_type_to_mark = "user" if reader_role == "admin" else "admin"
    from sqlalchemy import update

    stmt = (
        update(ChatMessage)
        .where(
            ChatMessage.room_id == room_id,
            ChatMessage.sender_type == sender_type_to_mark,
            ChatMessage.delivery_status != "read",
        )
        .values(delivery_status="read")
    )
    result = await session.execute(stmt)
    await session.flush()
    if result.rowcount:
        logger.info(
            "chat_messages_marked_read",
            room_id=room_id,
            reader_role=reader_role,
            count=result.rowcount,
        )
    return result.rowcount


async def mark_messages_delivered(session: AsyncSession, message_ids: list[str]) -> int:
    """Пометить сообщения как доставленные (sent → delivered)."""
    if not message_ids:
        return 0
    from sqlalchemy import update

    stmt = (
        update(ChatMessage)
        .where(
            ChatMessage.id.in_(message_ids),
            ChatMessage.delivery_status == "sent",
        )
        .values(delivery_status="delivered")
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount


async def get_total_unread_for_admin(session: AsyncSession) -> int:
    q = (
        select(func.count())
        .select_from(ChatMessage)
        .join(ChatRoom, ChatMessage.room_id == ChatRoom.id)
        .where(
            ChatRoom.type.in_(STAFF_ROOM_TYPES),
            ChatMessage.sender_type == "user",
            ChatMessage.delivery_status != "read",
            ChatMessage.deleted_at.is_(None),
        )
    )
    return (await session.execute(q)).scalar() or 0


async def get_total_unread_for_partner(session: AsyncSession, partner_id: str) -> int:
    q = (
        select(func.count())
        .select_from(ChatMessage)
        .join(ChatRoom, ChatMessage.room_id == ChatRoom.id)
        .where(
            ChatRoom.type.in_(STAFF_ROOM_TYPES),
            ChatRoom.partner_id == partner_id,
            ChatMessage.sender_type == "admin",
            ChatMessage.delivery_status != "read",
            ChatMessage.deleted_at.is_(None),
        )
    )
    return (await session.execute(q)).scalar() or 0


async def get_ai_response(text: str) -> str:
    """Stub AI assistant — returns a canned response.
    In production, this would call an LLM API (OpenAI, etc.)."""
    responses = {
        "помощь": "Я готов помочь! Какой у вас вопрос по процедуре банкротства?",
        "статус": "Чтобы узнать статус клиента, перейдите в раздел 'Мои клиенты' и выберите нужного.",
        "документы": "Для генерации документов перейдите на страницу клиента и нажмите 'Документы'.",
    }
    text_lower = text.lower()
    for key, response in responses.items():
        if key in text_lower:
            return response
    return (
        "Спасибо за ваш вопрос! Я — виртуальный помощник URITECH. "
        "Могу помочь с вопросами о статусах клиентов, документах и процедуре банкротства. "
        "Уточните, пожалуйста, ваш вопрос."
    )
