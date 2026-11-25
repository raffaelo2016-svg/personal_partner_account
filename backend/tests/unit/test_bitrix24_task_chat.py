from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.task_chat import (
    build_task_message_payload,
    chat_user_names,
    complete_task_message_projection,
    decorate_task_message,
    execute_task_message,
    import_task_chat_messages,
    is_system_message,
    normalize_chat_dialog,
    retry_unsent_task_messages,
    schedule_task_message,
    task_message_author_label,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.partner import Partner
from app.models.task import Task
from app.models.task_workspace import TaskMessage
from app.models.user import User
from app.services.task_service import send_task_message


async def _installation(db: AsyncSession) -> BitrixInstallation:
    installation = BitrixInstallation(
        member_id=f"member-{uuid4()}",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint="https://example.bitrix24.ru/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"access",
        refresh_token_encrypted=b"refresh",
        status="L",
    )
    db.add(installation)
    await db.flush()
    return installation


async def _partner_task(db: AsyncSession) -> tuple[User, Partner, Task]:
    admin = User(email=f"admin-{uuid4()}@example.test", hashed_password="hash", role="admin")
    partner_user = User(email=f"partner-{uuid4()}@example.test", hashed_password="hash", role="partner")
    db.add_all([admin, partner_user])
    await db.flush()
    partner = Partner(
        user_id=partner_user.id,
        company_name="ООО Ромашка",
        director_name="Иван Петров",
        inn="7701234567",
        phone="+71234567890",
        status="active",
    )
    db.add(partner)
    await db.flush()
    task = Task(
        partner_id=partner.id,
        title="Собрать документы",
        assigned_to="partner",
        created_by=admin.id,
        bitrix_task_id="31821",
        bitrix_chat_dialog_id="chat55137",
    )
    db.add(task)
    await db.flush()
    return partner_user, partner, task


def _chat_payload() -> dict:
    return {
        "messages": [
            {"id": 2548302, "author_id": 56, "date": "2026-11-25T09:39:11+03:00", "text": "Заявка в банк направлена"},
            {"id": 2548297, "author_id": 0, "date": "2026-11-25T09:38:56+03:00", "text": "начал выполнять задачу"},
            {"id": 2520879, "author_id": 44, "date": "2026-11-20T09:59:12+03:00", "text": "Откроем спецсчёт"},
        ],
        "users": [
            {"id": 56, "name": "Тамара Протацкая"},
            {"id": 44, "name": "Ангелина Савина"},
        ],
    }


def test_chat_dialog_normalization():
    assert normalize_chat_dialog(55137) == "chat55137"
    assert normalize_chat_dialog("chat55137") == "chat55137"
    assert normalize_chat_dialog("0") is None
    assert normalize_chat_dialog(None) is None


def test_system_messages_are_detected_by_author():
    assert is_system_message({"author_id": 0}) is True
    assert is_system_message({"author_id": 56}) is False


def test_chat_users_are_mapped_to_names():
    assert chat_user_names(_chat_payload()) == {"56": "Тамара Протацкая", "44": "Ангелина Савина"}


def test_outgoing_text_keeps_author_visible_in_bitrix():
    assert decorate_task_message("Иван Петров (партнёр)", "Добрый день") == "Иван Петров (партнёр): Добрый день"
    assert decorate_task_message("  ", "Добрый день") == "Добрый день"


def test_payload_uses_task_dialog():
    assert build_task_message_payload("chat55137", "Привет") == {
        "DIALOG_ID": "chat55137",
        "MESSAGE": "Привет",
        "SYSTEM": "N",
    }


@pytest.mark.asyncio
async def test_import_skips_system_messages_and_does_not_duplicate(db_session: AsyncSession):
    await _installation(db_session)
    _, _, task = await _partner_task(db_session)
    client = AsyncMock()
    client.call.return_value = _chat_payload()

    first = await import_task_chat_messages(db_session, client=client)
    assert first["imported"] == 2
    assert first["skipped"] == 1

    imported = list(
        (
            await db_session.scalars(
                select(TaskMessage).where(TaskMessage.task_id == task.id).order_by(TaskMessage.created_at)
            )
        ).all()
    )
    assert [message.text for message in imported] == ["Откроем спецсчёт", "Заявка в банк направлена"]
    assert [message.external_author_name for message in imported] == ["Ангелина Савина", "Тамара Протацкая"]
    assert all(message.origin == "bitrix" for message in imported)
    assert all(message.author_id is None for message in imported)

    second = await import_task_chat_messages(db_session, client=client)
    assert second["imported"] == 0


@pytest.mark.asyncio
async def test_outgoing_message_goes_to_task_chat_queue(db_session: AsyncSession):
    await _installation(db_session)
    partner_user, _, task = await _partner_task(db_session)
    message = TaskMessage(task_id=task.id, author_id=partner_user.id, text="Добрый день")
    db_session.add(message)
    await db_session.flush()

    queued = await schedule_task_message(
        db_session,
        message,
        task,
        text_for_bitrix=decorate_task_message("Иван Петров (партнёр)", message.text),
    )

    assert queued is True
    operation = await db_session.scalar(
        select(BitrixOutboxOperation).where(BitrixOutboxOperation.local_entity_id == message.id)
    )
    assert operation is not None
    assert operation.bitrix_method == "im.message.add"
    assert operation.payload["DIALOG_ID"] == "chat55137"
    assert operation.payload["MESSAGE"] == "Иван Петров (партнёр): Добрый день"
    assert message.bitrix_sync_status == "pending"


@pytest.mark.asyncio
async def test_sent_message_remembers_bitrix_id(db_session: AsyncSession):
    installation = await _installation(db_session)
    partner_user, _, task = await _partner_task(db_session)
    message = TaskMessage(task_id=task.id, author_id=partner_user.id, text="Привет")
    db_session.add(message)
    await db_session.flush()
    operation = BitrixOutboxOperation(
        member_id=installation.member_id,
        operation_key=f"task_message:send:{message.id}:v1",
        local_entity_type="task_message",
        local_entity_id=message.id,
        bitrix_method="im.message.add",
        payload=build_task_message_payload("chat55137", "Привет"),
        status="completed",
        result_reference="2549001",
    )
    db_session.add(operation)
    await db_session.flush()

    await complete_task_message_projection(db_session, operation)

    assert message.bitrix_message_id == "2549001"
    assert message.bitrix_sync_status == "synced"


@pytest.mark.asyncio
async def test_unsent_message_is_queued_once_dialog_is_known(db_session: AsyncSession):
    await _installation(db_session)
    partner_user, _, task = await _partner_task(db_session)
    message = TaskMessage(
        task_id=task.id,
        author_id=partner_user.id,
        text="Ждём ответа",
        bitrix_sync_status="not_scheduled",
        bitrix_sync_error_code="TASK_CHAT_NOT_RESOLVED",
    )
    db_session.add(message)
    await db_session.flush()

    assert await retry_unsent_task_messages(db_session, task) == 1
    assert message.bitrix_sync_status == "pending"


@pytest.mark.asyncio
async def test_author_label_names_partner_and_uritech(db_session: AsyncSession):
    partner_user, partner, task = await _partner_task(db_session)
    admin = User(email="evgeny@uritech.ru", hashed_password="hash", role="admin")
    db_session.add(admin)
    await db_session.flush()

    assert await task_message_author_label(db_session, partner_user, task) == "Иван Петров (партнёр)"
    assert await task_message_author_label(db_session, admin, task) == "evgeny (ЮРИТЕХ)"


@pytest.mark.asyncio
async def test_send_adds_integration_user_to_chat_on_access_denied(db_session: AsyncSession):
    installation = await _installation(db_session)
    partner_user, _, task = await _partner_task(db_session)
    message = TaskMessage(task_id=task.id, author_id=partner_user.id, text="Привет")
    db_session.add(message)
    await db_session.flush()
    operation = BitrixOutboxOperation(
        member_id=installation.member_id,
        operation_key=f"task_message:send:{message.id}:v1",
        local_entity_type="task_message",
        local_entity_id=message.id,
        bitrix_method="im.message.add",
        payload=build_task_message_payload("chat55137", "Привет"),
        status="processing",
    )
    db_session.add(operation)
    await db_session.flush()
    client = AsyncMock()
    client.call.side_effect = [
        Bitrix24Error("ACCESS_DENIED", "no access"),
        {"ID": "57"},
        True,
        777,
    ]

    result = await execute_task_message(client, operation, db=db_session)

    assert result == 777
    assert client.call.await_args_list[1].args == ("profile", {})
    assert client.call.await_args_list[2].args == ("im.chat.user.add", {"CHAT_ID": 55137, "USERS": [57]})
    assert installation.installed_by_user_id == 57


@pytest.mark.asyncio
async def test_cabinet_message_is_queued_by_task_service(db_session: AsyncSession):
    await _installation(db_session)
    partner_user, partner, task = await _partner_task(db_session)

    sent = await send_task_message(
        db_session,
        str(task.id),
        user_id=str(partner_user.id),
        partner_id=str(partner.id),
        text="Подскажите, пожалуйста",
    )

    assert sent.text == "Подскажите, пожалуйста"
    operation = await db_session.scalar(
        select(BitrixOutboxOperation).where(BitrixOutboxOperation.local_entity_type == "task_message")
    )
    assert operation is not None
    assert operation.payload["MESSAGE"] == "Иван Петров (партнёр): Подскажите, пожалуйста"
    assert sent.created_at <= datetime.now(UTC)
