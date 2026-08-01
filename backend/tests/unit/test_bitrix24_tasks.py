from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.sync import _execute_operation
from app.integrations.bitrix24.task_setup_cli import _active_user_ids
from app.integrations.bitrix24.tasks import (
    TASK_ENTITY_TYPE,
    TASK_RESPONSIBLE_SETTING_PREFIX,
    build_task_create_payload,
    extract_task_event_reference,
    process_task_status_event,
    schedule_task_creation,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.partner import Partner
from app.models.settings import SystemSetting
from app.models.task import Task
from app.models.user import User


def _task(client_id=None, created_by=None) -> Task:
    return Task(
        id=uuid4(),
        client_id=client_id or uuid4(),
        title="Собрать документы",
        description="Проверить комплект",
        priority="high",
        assigned_to="partner",
        created_by=created_by or uuid4(),
        due_date=date(2026, 8, 10),
    )


def test_task_payload_contains_crm_link_and_external_id():
    task = _task()

    payload = build_task_create_payload(task, deal_id="456", responsible_id=123, creator_id=321)["fields"]

    assert payload["TITLE"] == task.title
    assert payload["RESPONSIBLE_ID"] == 123
    assert payload["CREATED_BY"] == 321
    assert payload["PRIORITY"] == "2"
    assert payload["UF_CRM_TASK"] == ["D_456"]
    assert payload["XML_ID"] == f"partner_cabinet:{task.id}"
    assert payload["DEADLINE"].endswith("+03:00")


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"FIELDS_AFTER": {"ID": "77"}}},
        {"data[FIELDS_AFTER][ID]": "77"},
    ],
)
def test_task_event_reference_supports_json_and_form_payloads(payload):
    assert extract_task_event_reference("ONTASKUPDATE", payload) == "77"
    assert extract_task_event_reference("ONCRMDEALUPDATE", payload) is None


@pytest.mark.asyncio
async def test_active_user_ids_do_not_expose_user_profiles():
    remote = AsyncMock()
    remote.list_all.return_value = [{"ID": "10", "NAME": "Скрыто"}, {"ID": "11", "ACTIVE": True}]

    result = await _active_user_ids(remote)

    assert result == {10, 11}


async def _saved_entities(
    db: AsyncSession,
    *,
    deal_synced: bool = True,
    responsible_configured: bool = True,
) -> tuple[Task, Client]:
    installation = BitrixInstallation(
        member_id="member-stage-5",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"encrypted-access",
        refresh_token_encrypted=b"encrypted-refresh",
        status="L",
    )
    user = User(email="stage5@example.test", hashed_password="hash", role="partner", is_active=True)
    db.add_all([installation, user])
    await db.flush()
    partner = Partner(
        user_id=user.id,
        company_name="ООО Тест",
        director_name="Тестов Тест Тестович",
        inn="7700000000",
        phone="+70000000000",
        status="active",
    )
    db.add(partner)
    await db.flush()
    client = Client(
        partner_id=partner.id,
        type="before_court",
        full_name="Клиент Тестовый",
        bitrix_deal_id="456" if deal_synced else None,
        bitrix_sync_status="synced" if deal_synced else "pending",
    )
    db.add(client)
    await db.flush()
    task = _task(client.id, user.id)
    db.add(task)
    if responsible_configured:
        db.add(SystemSetting(key=f"{TASK_RESPONSIBLE_SETTING_PREFIX}partner", value="123"))
    await db.flush()
    return task, client


@pytest.mark.asyncio
async def test_task_creation_is_queued_once(db_session: AsyncSession):
    task, _ = await _saved_entities(db_session)

    first = await schedule_task_creation(db_session, task)
    second = await schedule_task_creation(db_session, task)

    count = await db_session.scalar(select(func.count(BitrixOutboxOperation.id)))
    operation = await db_session.scalar(select(BitrixOutboxOperation))
    assert first is True
    assert second is False
    assert count == 1
    assert operation is not None
    assert operation.local_entity_type == TASK_ENTITY_TYPE
    assert task.bitrix_sync_status == "pending"


@pytest.mark.asyncio
async def test_task_is_not_assigned_when_role_mapping_is_missing(db_session: AsyncSession):
    task, _ = await _saved_entities(db_session, responsible_configured=False)

    queued = await schedule_task_creation(db_session, task)

    assert queued is False
    assert task.bitrix_sync_status == "not_scheduled"
    assert task.bitrix_sync_error_code == "RESPONSIBLE_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_task_waits_for_client_deal(db_session: AsyncSession):
    task, _ = await _saved_entities(db_session, deal_synced=False)

    queued = await schedule_task_creation(db_session, task)

    assert queued is False
    assert task.bitrix_sync_status == "pending"
    assert task.bitrix_sync_error_code == "CLIENT_NOT_SYNCED"


@pytest.mark.asyncio
async def test_create_recovers_existing_remote_task_before_retrying_add():
    local_id = uuid4()
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"task:create:{local_id}:v1",
        local_entity_type=TASK_ENTITY_TYPE,
        local_entity_id=local_id,
        bitrix_method="tasks.task.add",
        payload={"fields": {"XML_ID": f"partner_cabinet:{local_id}"}},
    )
    remote = AsyncMock()
    remote.call.return_value = {"tasks": [{"id": "888"}]}

    result = await _execute_operation(remote, operation)

    assert result == "888"
    remote.call.assert_awaited_once()
    assert remote.call.await_args.args[0] == "tasks.task.list"


@pytest.mark.asyncio
async def test_remote_completed_status_updates_local_task(db_session: AsyncSession):
    task, _ = await _saved_entities(db_session)
    db_session.add(
        BitrixEntityMap(
            member_id="member-stage-5",
            local_entity_type=TASK_ENTITY_TYPE,
            local_entity_id=task.id,
            bitrix_entity_type="task",
            bitrix_entity_id="888",
        )
    )
    receipt = BitrixInboundEvent(
        member_id="member-stage-5",
        event_key=uuid4().hex,
        event_name="ONTASKUPDATE",
        payload_hash=uuid4().hex,
        remote_entity_type=TASK_ENTITY_TYPE,
        remote_entity_id="888",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {"task": {"status": "5", "closedDate": "2026-08-02T12:00:00+03:00"}}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.tasks._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.tasks.Bitrix24Client", return_value=context),
    ):
        completed = await process_task_status_event(db_session, receipt)

    assert completed is True
    assert task.status == "completed"
    assert task.completed_at is not None
    assert receipt.status == "completed"
