from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_chat import broadcast_messages_read, broadcast_new_message
from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatRoomRead
from app.services.chat_service import (
    get_admin_messages,
    get_total_unread_for_admin,
    list_admin_rooms,
    mark_messages_read,
    send_message,
)

router = APIRouter(prefix="/admin/chat", tags=["admin-chat"])


@router.get("/rooms", response_model=list[ChatRoomRead])
async def admin_chat_rooms(
    search: str | None = Query(None, max_length=100),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    rooms = await list_admin_rooms(db, search=search)
    await db.commit()
    return rooms


@router.get("/unread-count")
async def admin_unread_count(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    count = await get_total_unread_for_admin(db)
    return {"unread_count": count}


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageRead])
async def admin_room_messages(
    room_id: str,
    limit: int = Query(50, le=100),  # noqa: B008
    before: str | None = Query(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    msgs = await get_admin_messages(db, room_id, limit=limit, before=before)
    count = await mark_messages_read(db, room_id, reader_role="admin")
    if count:
        await broadcast_messages_read(room_id, exclude_user_id=str(_current_user.id))
    await db.commit()
    return msgs


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageRead, status_code=201)
async def admin_post_message(
    room_id: str,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    msg = await send_message(db, room_id, str(current_user.id), "admin", body.text)
    await db.commit()

    await broadcast_new_message(
        {
            "id": msg.id,
            "room_id": msg.room_id,
            "sender_id": msg.sender_id,
            "sender_type": msg.sender_type,
            "text": msg.text,
            "created_at": str(msg.created_at),
        },
        exclude_user_id=str(current_user.id),
        room_id=room_id,
    )

    return msg
