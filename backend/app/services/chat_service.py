import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, NotFound
from app.models.chat import ChatMessage, ChatRoom
from app.schemas.chat import ChatMessageRead, ChatRoomRead

logger = structlog.get_logger()

ROOM_TYPES = ["admin", "arbitration_manager", "assistant", "ai_assistant"]


def _msg_to_read(m: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=str(m.id),
        room_id=str(m.room_id),
        sender_id=str(m.sender_id) if m.sender_id else None,
        sender_type=m.sender_type,
        text=m.text,
        delivery_status=m.delivery_status,
        created_at=m.created_at,
    )


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
            func.row_number()
            .over(
                partition_by=ChatMessage.room_id,
                order_by=ChatMessage.created_at.desc(),
            )
            .label("rn"),
        )
        .where(ChatMessage.room_id.in_(room_ids))
        .subquery()
    )
    last_msgs_q = select(last_msg_sub.c.room_id, last_msg_sub.c.text).where(last_msg_sub.c.rn == 1)
    last_msgs = {str(r.room_id): r.text for r in (await session.execute(last_msgs_q)).all()}

    # Один запрос: unread count per room
    unread_q = (
        select(ChatMessage.room_id, func.count().label("cnt"))
        .where(
            ChatMessage.room_id.in_(room_ids),
            ChatMessage.sender_type != "user",
            ChatMessage.delivery_status != "read",
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

    q = select(ChatMessage).where(ChatMessage.room_id == room_id)
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
) -> ChatMessageRead:
    room = await session.get(ChatRoom, room_id)
    if not room:
        raise NotFound("Chat room not found")
    if partner_id and str(room.partner_id) != partner_id:
        raise Forbidden("Access denied")

    msg = ChatMessage(
        room_id=room_id,
        sender_id=sender_id if sender_type != "bot" else None,
        sender_type=sender_type,
        text=text,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)

    logger.info("chat_message_sent", room_id=room_id, sender_type=sender_type)
    return _msg_to_read(msg)


async def list_admin_rooms(
    session: AsyncSession,
    *,
    search: str | None = None,
) -> list[ChatRoomRead]:
    """Все admin-чаты для панели администратора."""
    from datetime import UTC
    from datetime import datetime as dt

    from app.models.partner import Partner

    q = select(ChatRoom).where(ChatRoom.type == "admin")
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
            ChatMessage.created_at,
            func.row_number()
            .over(
                partition_by=ChatMessage.room_id,
                order_by=ChatMessage.created_at.desc(),
            )
            .label("rn"),
        )
        .where(ChatMessage.room_id.in_(room_ids))
        .subquery()
    )
    last_msgs_q = select(last_msg_sub.c.room_id, last_msg_sub.c.text, last_msg_sub.c.created_at).where(
        last_msg_sub.c.rn == 1
    )
    last_msgs = {str(r.room_id): (r.text, r.created_at) for r in (await session.execute(last_msgs_q)).all()}

    # Один запрос: unread count per room
    unread_q = (
        select(ChatMessage.room_id, func.count().label("cnt"))
        .where(
            ChatMessage.room_id.in_(room_ids),
            ChatMessage.sender_type == "user",
            ChatMessage.delivery_status != "read",
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
    if not room or room.type != "admin":
        raise NotFound("Admin chat room not found")

    q = select(ChatMessage).where(ChatMessage.room_id == room_id)
    if before:
        ref = await session.get(ChatMessage, before)
        if ref:
            q = q.where(ChatMessage.created_at < ref.created_at)

    q = q.order_by(ChatMessage.created_at.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [_msg_to_read(m) for m in reversed(rows)]


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
            ChatRoom.type == "admin",
            ChatMessage.sender_type == "user",
            ChatMessage.delivery_status != "read",
        )
    )
    return (await session.execute(q)).scalar() or 0


async def get_total_unread_for_partner(session: AsyncSession, partner_id: str) -> int:
    q = (
        select(func.count())
        .select_from(ChatMessage)
        .join(ChatRoom, ChatMessage.room_id == ChatRoom.id)
        .where(
            ChatRoom.type == "admin",
            ChatRoom.partner_id == partner_id,
            ChatMessage.sender_type == "admin",
            ChatMessage.delivery_status != "read",
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
