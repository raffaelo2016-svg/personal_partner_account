import html

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_chat import broadcast_messages_read, broadcast_new_message
from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageEventRead, ChatMessageRead, ChatRoomRead
from app.services.chat_service import (
    get_admin_message_events,
    get_admin_messages,
    get_total_unread_for_admin,
    list_admin_rooms,
    mark_messages_read,
    send_message,
    upload_chat_file,
)
from app.services.s3_service import delete_file_async

router = APIRouter(prefix="/admin/chat", tags=["admin-chat"])


def _message_payload(msg: ChatMessageRead) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "sender_id": msg.sender_id,
        "sender_type": msg.sender_type,
        "text": msg.text,
        "delivery_status": msg.delivery_status,
        "bitrix_sync_status": msg.bitrix_sync_status,
        "bitrix_sync_error_code": msg.bitrix_sync_error_code,
        "bitrix_message_id": msg.bitrix_message_id,
        "attachment_url": msg.attachment_url,
        "attachment_filename": msg.attachment_filename,
        "attachment_size": msg.attachment_size,
        "attachment_mime_type": msg.attachment_mime_type,
        "created_at": str(msg.created_at),
    }


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


@router.get("/rooms/{room_id}/events", response_model=list[ChatMessageEventRead])
async def admin_room_message_events(
    room_id: str,
    limit: int = Query(100, le=200),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    return await get_admin_message_events(db, room_id, limit=limit)


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageRead, status_code=201)
async def admin_post_message(
    room_id: str,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    msg = await send_message(db, room_id, str(current_user.id), "admin", body.text)
    await db.commit()

    await broadcast_new_message(_message_payload(msg), exclude_user_id=str(current_user.id), room_id=room_id)

    return msg


@router.post("/rooms/{room_id}/attachments", response_model=ChatMessageRead, status_code=201)
async def admin_post_attachment(
    room_id: str,
    text: str = Form(""),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    s3_key, filename, size, mime_type = await upload_chat_file(file)
    try:
        msg = await send_message(
            db,
            room_id,
            str(current_user.id),
            "admin",
            html.escape(text.strip(), quote=True) if text else "",
            attachment_s3_key=s3_key,
            attachment_filename=filename,
            attachment_size=size,
            attachment_mime_type=mime_type,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_file_async(s3_key)
        raise

    await broadcast_new_message(_message_payload(msg), exclude_user_id=str(current_user.id), room_id=room_id)
    return msg
