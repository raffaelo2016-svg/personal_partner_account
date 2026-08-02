from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.bitrix24.chat import (
    CHAT_FILE_METHOD,
    CHAT_MESSAGE_ENTITY_TYPE,
    execute_chat_message,
    import_message_event,
    normalize_dialog_id,
    record_message_change_event,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.chat import ChatMessage, ChatMessageEvent, ChatRoom
from app.models.partner import Partner
from app.models.user import User


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("123", "chat123"), ("chat123", "chat123"), ("sg42", "sg42")],
)
def test_dialog_id_normalization(raw: str, expected: str):
    assert normalize_dialog_id(raw) == expected


@pytest.mark.asyncio
async def test_outgoing_message_uses_linked_dialog():
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"chat:message:{uuid4()}:v1",
        local_entity_type=CHAT_MESSAGE_ENTITY_TYPE,
        local_entity_id=uuid4(),
        bitrix_method="im.message.add",
        payload={"DIALOG_ID": "chat123", "MESSAGE": "Hello", "SYSTEM": "N"},
    )
    remote = AsyncMock()
    remote.call.return_value = 5012

    result = await execute_chat_message(remote, operation)

    assert result == 5012
    remote.call.assert_awaited_once_with("im.message.add", operation.payload)


@pytest.mark.asyncio
async def test_outgoing_attachment_is_loaded_only_when_queue_runs():
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"chat:message:{uuid4()}:v1",
        local_entity_type=CHAT_MESSAGE_ENTITY_TYPE,
        local_entity_id=uuid4(),
        bitrix_method=CHAT_FILE_METHOD,
        payload={"dialog_id": "chat123", "s3_key": "uploads/file.pdf", "name": "report.pdf", "message": ""},
    )
    remote = AsyncMock()
    remote.call.return_value = {"messageId": 5013, "file": {"id": 138}}

    with patch(
        "app.integrations.bitrix24.chat.download_file_async",
        new=AsyncMock(return_value=b"%PDF-1.7"),
    ):
        result = await execute_chat_message(remote, operation)

    assert result["messageId"] == 5013
    method, payload = remote.call.await_args.args
    assert method == "im.v2.File.upload"
    assert payload["dialogId"] == "chat123"
    assert payload["fields"]["name"] == "report.pdf"
    assert payload["fields"]["content"] == "JVBERi0xLjc="


async def _partner_room(db_session: AsyncSession) -> ChatRoom:
    user = User(email=f"partner-{uuid4()}@example.test", hashed_password="hash", role="partner")
    db_session.add(user)
    await db_session.flush()
    partner = Partner(
        user_id=user.id,
        company_name="Test partner",
        director_name="Test director",
        inn="123456789012",
        phone="+70000000000",
        bitrix_chat_id="chat123",
    )
    db_session.add(partner)
    await db_session.flush()
    room = ChatRoom(partner_id=partner.id, type="admin")
    db_session.add(room)
    await db_session.commit()
    return room


def _message_event(remote_id: int = 5012) -> dict:
    return {
        "eventId": 2001,
        "type": "ONIMV2MESSAGEADD",
        "date": "2026-08-02T10:30:00+03:00",
        "data": {
            "message": {
                "id": remote_id,
                "chatId": 123,
                "authorId": 7,
                "date": "2026-08-02T10:30:00+03:00",
                "text": "Ответ <сотрудника>",
            },
            "chat": {"id": 123, "dialogId": "chat123"},
        },
    }


def _file_event(remote_id: int = 5014) -> dict:
    event = _message_event(remote_id)
    event["data"]["message"]["text"] = "Документ"
    event["data"]["message"]["params"] = {"files": [{"id": 138, "name": "report.pdf", "size": 9}]}
    return event


@pytest.mark.asyncio
async def test_incoming_message_is_imported_once_and_escaped(db_session: AsyncSession):
    room = await _partner_room(db_session)

    first = await import_message_event(db_session, _message_event())
    await db_session.commit()
    second = await import_message_event(db_session, _message_event())

    count = await db_session.scalar(select(func.count(ChatMessage.id)))
    assert first is not None
    assert first.room_id == room.id
    assert first.sender_type == "admin"
    assert first.origin == "bitrix"
    assert first.bitrix_message_id == "5012"
    assert first.text == "Ответ &lt;сотрудника&gt;"
    assert second is None
    assert count == 1


@pytest.mark.asyncio
async def test_unlinked_chat_event_is_ignored(db_session: AsyncSession):
    await _partner_room(db_session)
    event = _message_event(5013)
    event["data"]["chat"]["dialogId"] = "chat999"
    event["data"]["message"]["chatId"] = 999

    assert await import_message_event(db_session, event) is None


@pytest.mark.asyncio
async def test_incoming_attachment_metadata_is_saved(db_session: AsyncSession):
    await _partner_room(db_session)
    installation = AsyncMock()
    remote = AsyncMock()
    imported_attachment = ("uploads/imported.pdf", "report.pdf", 9, "application/pdf")

    with patch(
        "app.integrations.bitrix24.chat._import_attachment",
        new=AsyncMock(return_value=imported_attachment),
    ):
        message = await import_message_event(
            db_session,
            _file_event(),
            client=remote,
            installation=installation,
        )

    assert message is not None
    assert message.attachment_s3_key == "uploads/imported.pdf"
    assert message.attachment_filename == "report.pdf"
    assert message.attachment_size == 9
    assert message.attachment_mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_message_update_is_journaled_once_without_changing_local_text(db_session: AsyncSession):
    await _partner_room(db_session)
    db_session.add(
        BitrixInstallation(
            member_id="member",
            portal_domain="example.bitrix24.ru",
            client_endpoint="https://example.bitrix24.ru/rest/",
            server_endpoint="https://oauth.bitrix.info/rest/",
            access_token_encrypted=b"access",
            refresh_token_encrypted=b"refresh",
        )
    )
    original = await import_message_event(db_session, _message_event(5020))
    await db_session.commit()
    event = _message_event(5020)
    event["eventId"] = 2020
    event["type"] = "ONIMV2MESSAGEUPDATE"
    event["data"]["message"]["text"] = "Изменённый текст"

    first = await record_message_change_event(db_session, event, member_id="member")
    second = await record_message_change_event(db_session, event, member_id="member")
    await db_session.commit()

    journal_count = await db_session.scalar(select(func.count(ChatMessageEvent.id)))
    await db_session.refresh(original)
    assert first is True
    assert second is False
    assert journal_count == 1
    assert original.text == "Ответ &lt;сотрудника&gt;"
