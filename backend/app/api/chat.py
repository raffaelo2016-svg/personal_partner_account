import html

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_chat import broadcast_messages_read, broadcast_new_message
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatRoomRead
from app.services.s3_service import delete_file_async
from app.services.chat_service import (
    get_ai_response,
    get_messages,
    get_total_unread_for_partner,
    list_rooms,
    mark_messages_read,
    send_message,
    upload_chat_file,
)
from app.services.client_service import _get_partner_id_for_user

router = APIRouter(prefix="/chat", tags=["chat"])


def _message_payload(msg: ChatMessageRead) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "sender_id": msg.sender_id,
        "sender_type": msg.sender_type,
        "text": msg.text,
        "delivery_status": msg.delivery_status,
        "attachment_url": msg.attachment_url,
        "attachment_filename": msg.attachment_filename,
        "attachment_size": msg.attachment_size,
        "attachment_mime_type": msg.attachment_mime_type,
        "created_at": str(msg.created_at),
    }


@router.get("/rooms", response_model=list[ChatRoomRead])
async def chat_rooms(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    rooms = await list_rooms(db, partner_id)
    await db.commit()
    return rooms


@router.get("/unread-count")
async def partner_unread_count(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    count = await get_total_unread_for_partner(db, partner_id)
    return {"unread_count": count}


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageRead])
async def room_messages(
    room_id: str,
    limit: int = Query(50, le=100),  # noqa: B008
    before: str | None = Query(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    msgs = await get_messages(db, room_id, partner_id, limit=limit, before=before)
    count = await mark_messages_read(db, room_id, reader_role="partner")
    if count:
        await broadcast_messages_read(room_id, exclude_user_id=str(current_user.id))
    await db.commit()
    return msgs


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageRead, status_code=201)
async def post_message(
    room_id: str,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    msg = await send_message(
        db,
        room_id,
        str(current_user.id),
        "user",
        body.text,
        partner_id=partner_id,
    )

    from app.models.chat import ChatRoom

    room = await db.get(ChatRoom, room_id)
    ai_msg = None
    if room and room.type == "ai_assistant":
        ai_text = await get_ai_response(body.text)
        ai_msg = await send_message(db, room_id, str(current_user.id), "bot", ai_text)

    await db.commit()

    await broadcast_new_message(_message_payload(msg), exclude_user_id=str(current_user.id), room_id=room_id)
    if ai_msg:
        await broadcast_new_message(_message_payload(ai_msg), room_id=room_id)

    return msg


@router.post("/rooms/{room_id}/attachments", response_model=ChatMessageRead, status_code=201)
async def post_attachment(
    room_id: str,
    text: str = Form(""),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    s3_key, filename, size, mime_type = await upload_chat_file(file)
    try:
        msg = await send_message(
            db,
            room_id,
            str(current_user.id),
            "user",
            html.escape(text.strip(), quote=True) if text else "",
            partner_id=partner_id,
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
