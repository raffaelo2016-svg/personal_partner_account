from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.sync import _execute_operation
from app.integrations.bitrix24.task_setup_cli import _active_user_ids, _values_to_apply
from app.integrations.bitrix24.tasks import (
    TASK_ADD_EVENT,
    TASK_ENTITY_TYPE,
    TASK_RESPONSIBLE_SETTING_PREFIX,
    build_task_create_payload,
    extract_task_event_reference,
    process_task_status_event,
    reconcile_remote_tasks,
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
    assert extract_task_event_reference(TASK_ADD_EVENT, payload) == "77"
    assert extract_task_event_reference("ONCRMDEALUPDATE", payload) is None


@pytest.mark.asyncio
async def test_active_user_ids_do_not_expose_user_profiles():
    remote = AsyncMock()
    remote.list_all.return_value = [{"ID": "10", "NAME": "Скрыто"}, {"ID": "11", "ACTIVE": True}]

    result = await _active_user_ids(remote)

    assert result == {10, 11}


def test_installer_fallback_fills_only_missing_roles():
    result = _values_to_apply(
        {"partner": None, "admin": None, "creator": None},
        {"partner": 20},
        fill_missing_with_installer=True,
        installer_id=10,
    )

    assert result == {"admin": 10, "creator": 10}


def test_explicit_responsible_has_priority_over_installer_fallback():
    result = _values_to_apply(
        {"partner": 30, "admin": None, "creator": None},
        {},
        fill_missing_with_installer=True,
        installer_id=10,
    )

    assert result == {"partner": 30, "admin": 10, "creator": 10}


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
    db_session.add_all(
        [
            SystemSetting(key=f"{TASK_RESPONSIBLE_SETTING_PREFIX}admin", value="456"),
            BitrixEntityMap(
                member_id="member-stage-5",
                local_entity_type=TASK_ENTITY_TYPE,
                local_entity_id=task.id,
                bitrix_entity_type="task",
                bitrix_entity_id="888",
            ),
        ]
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
    remote.call.return_value = {
        "task": {
            "title": "Подтвердить комплект",
            "description": "Проверка завершена",
            "status": "5",
            "priority": "0",
            "deadline": "2026-08-14T18:00:00+03:00",
            "closedDate": "2026-08-02T12:00:00+03:00",
            "responsibleId": "456",
        }
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.tasks._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.tasks.Bitrix24Client", return_value=context),
    ):
        completed = await process_task_status_event(db_session, receipt)

    assert completed is True
    assert task.title == "Подтвердить комплект"
    assert task.description == "Проверка завершена"
    assert task.status == "completed"
    assert task.priority == "low"
    assert task.due_date == date(2026, 8, 14)
    assert task.assigned_to == "admin"
    assert task.completed_at is not None
    assert task.bitrix_synced_at is not None
    assert receipt.status == "completed"


@pytest.mark.asyncio
async def test_periodic_reconciliation_recovers_missed_task_update(db_session: AsyncSession):
    task, _ = await _saved_entities(db_session)
    mapping = BitrixEntityMap(
        member_id="member-stage-5",
        local_entity_type=TASK_ENTITY_TYPE,
        local_entity_id=task.id,
        bitrix_entity_type="task",
        bitrix_entity_id="904",
    )
    db_session.add(mapping)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {
        "task": {
            "id": "904",
            "title": "Исправить заявление",
            "description": "Получить подпись клиента",
            "status": "3",
            "priority": "2",
            "deadline": "2026-08-20T18:00:00+03:00",
            "responsibleId": "123",
        }
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.tasks._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.tasks.Bitrix24Client", return_value=context),
    ):
        result = await reconcile_remote_tasks(db_session, limit=5)

    assert result == {"claimed": 1, "completed": 1, "failed": 0}
    assert task.title == "Исправить заявление"
    assert task.description == "Получить подпись клиента"
    assert task.status == "in_progress"
    assert task.priority == "high"
    assert task.due_date == date(2026, 8, 20)
    assert task.bitrix_sync_status == "synced"
    assert mapping.last_verified_at is not None


@pytest.mark.asyncio
async def test_remote_added_task_is_imported_for_known_client(db_session: AsyncSession):
    existing_task, client = await _saved_entities(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-stage-5",
        event_key=uuid4().hex,
        event_name=TASK_ADD_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type=TASK_ENTITY_TYPE,
        remote_entity_id="901",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {
        "task": {
            "id": "901",
            "title": "Получить справку",
            "description": "Запросить документ",
            "status": "2",
            "priority": "2",
            "deadline": "2026-08-12T18:00:00+03:00",
            "xmlId": "",
            "ufCrmTask": ["D_456"],
        }
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.tasks._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.tasks.Bitrix24Client", return_value=context),
    ):
        completed = await process_task_status_event(db_session, receipt)

    imported = await db_session.scalar(select(Task).where(Task.bitrix_task_id == "901"))
    mapping = await db_session.scalar(
        select(BitrixEntityMap).where(
            BitrixEntityMap.member_id == "member-stage-5",
            BitrixEntityMap.bitrix_entity_type == TASK_ENTITY_TYPE,
            BitrixEntityMap.bitrix_entity_id == "901",
        )
    )
    assert completed is True
    assert imported is not None
    assert imported.id != existing_task.id
    assert imported.client_id == client.id
    assert imported.title == "Получить справку"
    assert imported.description == "Запросить документ"
    assert imported.status == "pending"
    assert imported.priority == "high"
    assert imported.assigned_to == "partner"
    assert imported.due_date == date(2026, 8, 12)
    assert imported.bitrix_sync_status == "synced"
    assert mapping is not None
    assert mapping.local_entity_id == imported.id
    assert receipt.status == "completed"


@pytest.mark.asyncio
async def test_remote_added_task_from_cabinet_is_not_imported_again(db_session: AsyncSession):
    existing_task, _ = await _saved_entities(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-stage-5",
        event_key=uuid4().hex,
        event_name=TASK_ADD_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type=TASK_ENTITY_TYPE,
        remote_entity_id="902",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {
        "task": {
            "id": "902",
            "title": "Собственная задача",
            "status": "2",
            "xmlId": f"partner_cabinet:{existing_task.id}",
            "ufCrmTask": ["D_456"],
        }
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.tasks._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.tasks.Bitrix24Client", return_value=context),
    ):
        completed = await process_task_status_event(db_session, receipt)

    imported = await db_session.scalar(select(Task).where(Task.bitrix_task_id == "902"))
    assert completed is True
    assert imported is None
    assert receipt.status == "ignored"


@pytest.mark.asyncio
async def test_unmapped_update_does_not_import_old_task(db_session: AsyncSession):
    await _saved_entities(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-stage-5",
        event_key=uuid4().hex,
        event_name="ONTASKUPDATE",
        payload_hash=uuid4().hex,
        remote_entity_type=TASK_ENTITY_TYPE,
        remote_entity_id="903",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {
        "task": {
            "id": "903",
            "title": "Старая задача",
            "status": "2",
            "xmlId": "",
            "ufCrmTask": ["D_456"],
        }
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.tasks._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.tasks.Bitrix24Client", return_value=context),
    ):
        completed = await process_task_status_event(db_session, receipt)

    imported = await db_session.scalar(select(Task).where(Task.bitrix_task_id == "903"))
    assert completed is True
    assert imported is None
    assert receipt.status == "ignored"
