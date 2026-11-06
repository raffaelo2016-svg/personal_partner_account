from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24 import task_setup_cli, tasks
from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.sync import event_fingerprint
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.partner import Partner
from app.models.task import Task


@pytest.fixture
def setup_db() -> None:
    """Projection/parser unit tests mock persistence and do not need PostgreSQL."""


def _partner(item_id: str = "101") -> Partner:
    return Partner(
        id=uuid4(),
        user_id=uuid4(),
        company_name="Тестовый партнёр",
        director_name="Тестовый директор",
        inn="7700000000",
        phone="+70000000000",
        status="active",
        bitrix_partner_item_id=item_id,
    )


def _installation() -> BitrixInstallation:
    return BitrixInstallation(
        member_id="member-partner-tasks",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"unused-test-value",
        refresh_token_encrypted=b"unused-test-value",
        status="L",
    )


def _receipt(event_name: str = tasks.TASK_ADD_EVENT, remote_id: str = "700") -> BitrixInboundEvent:
    return BitrixInboundEvent(
        id=uuid4(),
        member_id="member-partner-tasks",
        event_key=uuid4().hex,
        event_name=event_name,
        payload_hash=uuid4().hex,
        remote_entity_type=tasks.TASK_ENTITY_TYPE,
        remote_entity_id=remote_id,
        attempts=0,
    )


def _remote_task(**fields) -> dict:
    return {
        "id": "700",
        "title": "Подписать договор",
        "description": "Подготовить &#91;документ&#93;",
        "status": "2",
        "priority": "2",
        "tags": ["ЛКП"],
        "ufCrmTask": [f"T{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID:x}_101"],
        **fields,
    }


def _mock_db() -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.scalar.return_value = None

    async def assign_identity() -> None:
        for call in db.add.call_args_list:
            entity = call.args[0]
            if getattr(entity, "id", None) is None:
                entity.id = uuid4()

    db.flush.side_effect = assign_identity
    return db


def _rows(entities: list) -> MagicMock:
    result = MagicMock()
    result.all.return_value = entities
    return result


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (False, None),
        ("2026-10-15T18:30:00+03:00", datetime(2026, 10, 15, 15, 30, tzinfo=UTC)),
        ("2026-10-15T22:30:00Z", datetime(2026, 10, 15, 22, 30, tzinfo=UTC)),
        ("2026-10-15T18:30:00", datetime(2026, 10, 15, 15, 30, tzinfo=UTC)),
    ],
)
def test_deadline_is_exact_utc_or_absent(value, expected):
    assert tasks._parse_due_at(value) == expected


def test_invalid_deadline_is_rejected_instead_of_replaced_with_today():
    with pytest.raises(ValueError):
        tasks._parse_due_at("not-a-date")


def test_flat_form_events_for_different_tasks_at_same_timestamp_are_distinct():
    first_payload = {"event": tasks.TASK_UPDATE_EVENT, "ts": "1792062000", "data[FIELDS_AFTER][ID]": "700"}
    second_payload = {**first_payload, "data[FIELDS_AFTER][ID]": "701"}

    first_key, first_hash = event_fingerprint(first_payload)
    second_key, second_hash = event_fingerprint(second_payload)

    assert first_key != second_key
    assert first_hash != second_hash
    assert event_fingerprint(first_payload) == (first_key, first_hash)


def test_task_payload_uses_partner_smart_process_and_preserves_exact_deadline():
    task = Task(
        id=uuid4(),
        partner_id=uuid4(),
        client_id=None,
        created_by=uuid4(),
        title="Подписать договор",
        assigned_to="partner",
        priority="medium",
        due_date=date(2026, 10, 16),
        due_at=datetime(2026, 10, 15, 22, 30, tzinfo=UTC),
    )

    payload = tasks.build_task_create_payload(task, partner_item_id="101", responsible_id=42, creator_id=None)["fields"]

    assert payload["UF_CRM_TASK"] == [f"T{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID:x}_101"]
    assert datetime.fromisoformat(payload["DEADLINE"]) == task.due_at


def test_task_payload_does_not_invent_deadline():
    task = Task(id=uuid4(), title="Без срока", priority="medium", due_date=None, due_at=None)

    payload = tasks.build_task_create_payload(task, deal_id="456", responsible_id=42, creator_id=None)["fields"]

    assert not payload.get("DEADLINE")


@pytest.mark.asyncio
@pytest.mark.parametrize("tag", ["ЛКП", "лкп", "Лкп"])
async def test_explicit_publication_imports_general_partner_task(tag):
    db = _mock_db()
    partner = _partner()
    receipt = _receipt()
    remote_task = _remote_task(tags=[tag], deadline="2026-10-15T22:30:00Z")

    with patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(partner, None, None))):
        assert await tasks._import_remote_task(
            db, receipt=receipt, remote_task=remote_task, installation=_installation()
        )

    imported = next(call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Task))
    assert imported.partner_id == partner.id
    assert imported.client_id is None
    assert imported.created_by == partner.user_id
    assert imported.assigned_to == "partner"
    assert imported.title == "Подписать договор"
    assert imported.description == "Подготовить [документ]"
    assert imported.due_at == datetime(2026, 10, 15, 22, 30, tzinfo=UTC)
    assert imported.due_date == date(2026, 10, 16)
    assert imported.bitrix_task_id == "700"
    assert imported.bitrix_sync_status == "synced"
    assert receipt.status == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("tags", [None, [], ["внутренняя"], ["ЛКП-внутренняя"]])
async def test_internal_task_without_separate_publication_tag_is_not_imported(tags):
    db = _mock_db()
    receipt = _receipt()

    with patch.object(tasks, "_remote_task_target", new=AsyncMock()) as target:
        assert await tasks._import_remote_task(
            db,
            receipt=receipt,
            remote_task=_remote_task(tags=tags),
            installation=_installation(),
        )

    assert receipt.status == "ignored"
    target.assert_not_awaited()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_partner_task_without_deadline_stays_without_deadline():
    db = _mock_db()
    receipt = _receipt()

    with patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(_partner(), None, None))):
        assert await tasks._import_remote_task(
            db, receipt=receipt, remote_task=_remote_task(deadline=""), installation=_installation()
        )

    imported = next(call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Task))
    assert imported.due_date is None
    assert imported.due_at is None


@pytest.mark.asyncio
async def test_unmapped_update_can_publish_task_after_adding_tag():
    db = _mock_db()
    db.scalar.side_effect = [_installation(), None, None]
    remote = AsyncMock()
    remote.call.return_value = {"task": _remote_task()}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    receipt = _receipt(tasks.TASK_UPDATE_EVENT)

    with (
        patch.object(tasks, "_installation_token", new=AsyncMock(return_value="unused")),
        patch.object(tasks, "Bitrix24Client", return_value=context),
        patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(_partner(), None, None))),
    ):
        assert await tasks.process_task_status_event(db, receipt)

    assert receipt.status == "completed"
    assert sum(isinstance(call.args[0], Task) for call in db.add.call_args_list) == 1


@pytest.mark.asyncio
async def test_mapped_repeat_updates_existing_task_without_duplicate():
    db = _mock_db()
    partner = _partner()
    task = Task(
        id=uuid4(),
        partner_id=partner.id,
        client_id=None,
        created_by=partner.user_id,
        title="Первоначальная задача",
        status="pending",
        assigned_to="partner",
        due_at=datetime(2026, 10, 15, 15, 0, tzinfo=UTC),
        due_date=date(2026, 10, 15),
        bitrix_task_id="700",
        bitrix_imported=True,
    )
    mapping = BitrixEntityMap(
        member_id="member-partner-tasks",
        local_entity_type=tasks.TASK_ENTITY_TYPE,
        local_entity_id=task.id,
        bitrix_entity_type=tasks.TASK_ENTITY_TYPE,
        bitrix_entity_id="700",
    )
    db.scalar.side_effect = [_installation(), mapping]
    db.get.return_value = task
    remote = AsyncMock()
    remote.call.return_value = {"task": _remote_task(title="Срок снят", deadline="")}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    receipt = _receipt()

    with (
        patch.object(tasks, "_installation_token", new=AsyncMock(return_value="unused")),
        patch.object(tasks, "Bitrix24Client", return_value=context),
        patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(partner, None, None))),
    ):
        assert await tasks.process_task_status_event(db, receipt)

    db.add.assert_not_called()
    assert task.title == "Срок снят"
    assert task.due_at is None
    assert task.due_date is None
    assert receipt.status == "completed"
    assert mapping.last_verified_at is not None


@pytest.mark.asyncio
async def test_smart_process_reference_resolves_general_partner_target():
    db = _mock_db()
    partner = _partner()
    db.scalars.return_value = _rows([partner])

    resolved_partner, client, error = await tasks._remote_task_target(db, _remote_task())

    assert resolved_partner is partner
    assert client is None
    assert error is None
    db.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_deal_reference_resolves_client_and_its_partner():
    db = _mock_db()
    partner = _partner()
    client = Client(id=uuid4(), partner_id=partner.id, type="before_court", full_name="Тест", bitrix_deal_id="456")
    db.scalars.return_value = _rows([client])
    db.get.return_value = partner

    resolved_partner, resolved_client, error = await tasks._remote_task_target(db, _remote_task(ufCrmTask=["D_456"]))

    assert resolved_partner is partner
    assert resolved_client is client
    assert error is None


@pytest.mark.asyncio
async def test_conflicting_partner_and_client_links_are_rejected():
    db = _mock_db()
    partner = _partner()
    client = Client(id=uuid4(), partner_id=uuid4(), type="before_court", full_name="Другой клиент")
    db.scalars.side_effect = [_rows([client]), _rows([partner])]

    resolved_partner, resolved_client, error = await tasks._remote_task_target(
        db,
        _remote_task(ufCrmTask=["D_456", f"T{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID:x}_101"]),
    )

    assert resolved_partner is None
    assert resolved_client is None
    assert error == "AMBIGUOUS_TASK_PARTNER"


@pytest.mark.asyncio
async def test_multiple_client_links_for_same_partner_do_not_select_arbitrary_client():
    db = _mock_db()
    partner = _partner()
    clients = [
        Client(id=uuid4(), partner_id=partner.id, type="before_court", full_name="Первый клиент"),
        Client(id=uuid4(), partner_id=partner.id, type="before_court", full_name="Второй клиент"),
    ]
    db.scalars.return_value = _rows(clients)
    db.get.return_value = partner

    resolved_partner, resolved_client, error = await tasks._remote_task_target(
        db, _remote_task(ufCrmTask=["D_456", "D_457"])
    )

    assert resolved_partner is partner
    assert resolved_client is None
    assert error is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("references", "error"),
    [
        ([], "CRM_REFERENCE_REQUIRED"),
        (["CO_123"], "CRM_REFERENCE_REQUIRED"),
        (["D_456"], "CLIENT_NOT_FOUND"),
        ([f"T{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID:x}_101"], "PARTNER_NOT_FOUND"),
    ],
)
async def test_missing_crm_target_does_not_route_task_to_any_partner(references, error):
    db = _mock_db()
    db.scalars.return_value = _rows([])

    partner, client, result_error = await tasks._remote_task_target(db, _remote_task(ufCrmTask=references))

    assert partner is None
    assert client is None
    assert result_error == error


@pytest.mark.asyncio
async def test_ambiguous_task_import_fails_without_writing_task():
    db = _mock_db()
    receipt = _receipt()
    with patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(None, None, "AMBIGUOUS_TASK_PARTNER"))):
        assert not await tasks._import_remote_task(
            db, receipt=receipt, remote_task=_remote_task(), installation=_installation()
        )

    assert receipt.error_code == "AMBIGUOUS_TASK_PARTNER"
    assert receipt.status == "failed"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_deadline_does_not_overwrite_existing_task_fields():
    db = _mock_db()
    existing_deadline = datetime(2026, 10, 15, 15, 0, tzinfo=UTC)
    task = Task(
        id=uuid4(),
        title="Сохранённая задача",
        status="pending",
        due_at=existing_deadline,
        due_date=date(2026, 10, 15),
        bitrix_imported=True,
    )

    with patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(_partner(), None, None))):
        assert not await tasks._apply_remote_task_fields(db, task, _remote_task(deadline="broken"))

    assert task.title == "Сохранённая задача"
    assert task.due_at == existing_deadline
    assert task.due_date == date(2026, 10, 15)


@pytest.mark.asyncio
async def test_discovery_imports_tagged_task_when_add_event_was_missed():
    db = _mock_db()
    installation = _installation()
    receipt = _receipt()
    db.scalar.side_effect = [installation, None, receipt.id, None]

    async def persisted_entity(model, identity):
        if model is BitrixInboundEvent:
            return receipt
        return None

    db.get.side_effect = persisted_entity
    remote = AsyncMock()
    remote.list_all.return_value = [_remote_task(deadline=None)]
    context = AsyncMock()
    context.__aenter__.return_value = remote

    with (
        patch.object(tasks, "active_installation", new=AsyncMock(return_value=installation)),
        patch.object(tasks, "_installation_token", new=AsyncMock(return_value="unused")),
        patch.object(tasks, "Bitrix24Client", return_value=context),
        patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(_partner(), None, None))),
    ):
        result = await tasks.discover_remote_tasks(db)

    assert result == {"scanned": 1, "imported": 1, "updated": 0, "failed": 0}
    assert receipt.status == "completed"
    assert sum(isinstance(call.args[0], Task) for call in db.add.call_args_list) == 1
    filters = remote.list_all.await_args.args[1]["filter"]
    assert filters["TAG"] == "ЛКП"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "expected_deadline"),
    [
        ({"due_at": None, "due_date": None}, ""),
        (
            {"due_at": datetime(2026, 10, 15, 22, 30, tzinfo=UTC), "due_date": date(2026, 10, 16)},
            "2026-10-16T01:30:00+03:00",
        ),
    ],
)
async def test_admin_deadline_edit_is_sent_to_linked_bitrix_task(updates, expected_deadline):
    db = _mock_db()
    task = Task(
        id=uuid4(), bitrix_task_id="700", due_at=datetime(2026, 10, 15, 15, 0, tzinfo=UTC), due_date=date(2026, 10, 15)
    )
    remote = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = remote

    with (
        patch.object(tasks, "active_installation", new=AsyncMock(return_value=_installation())),
        patch.object(tasks, "_installation_token", new=AsyncMock(return_value="unused")),
        patch.object(tasks, "Bitrix24Client", return_value=context),
    ):
        await tasks.sync_task_fields(db, task, updates)

    remote.call.assert_awaited_once_with(
        "tasks.task.update", {"taskId": "700", "fields": {"DEADLINE": expected_deadline}}
    )
    assert task.bitrix_sync_status == "synced"
    assert task.bitrix_synced_at is not None


@pytest.mark.asyncio
async def test_admin_bitrix_edit_failure_is_propagated_without_accepting_local_changes():
    db = _mock_db()
    task = Task(id=uuid4(), bitrix_task_id="700", title="Сохранённое название", bitrix_synced_at=None)
    remote = AsyncMock()
    remote.call.side_effect = Bitrix24Error("TIMEOUT", "Test failure")
    context = AsyncMock()
    context.__aenter__.return_value = remote

    with (
        patch.object(tasks, "active_installation", new=AsyncMock(return_value=_installation())),
        patch.object(tasks, "_installation_token", new=AsyncMock(return_value="unused")),
        patch.object(tasks, "Bitrix24Client", return_value=context),
        pytest.raises(Bitrix24Error, match="TIMEOUT"),
    ):
        await tasks.sync_task_fields(db, task, {"title": "Изменение не сохранено"})

    assert task.title == "Сохранённое название"
    assert task.bitrix_synced_at is None


@pytest.mark.asyncio
async def test_partner_task_binding_dry_run_does_not_modify_portal():
    remote = AsyncMock()
    remote.call.return_value = {
        "type": {"id": 22, "isUseInUserfieldEnabled": "N", "linkedUserFields": {"CRM_LEAD|UF_TEST": "true"}}
    }

    assert not await task_setup_cli.ensure_partner_task_binding(remote, apply=False)

    remote.call.assert_awaited_once_with(
        "crm.type.getByEntityTypeId", {"entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}
    )


@pytest.mark.asyncio
async def test_partner_task_binding_preserves_other_links_and_verifies_saved_configuration():
    remote = AsyncMock()
    remote.call.side_effect = [
        {"type": {"id": 22, "isUseInUserfieldEnabled": "N", "linkedUserFields": {"CRM_LEAD|UF_TEST": "true"}}},
        {},
        {
            "type": {
                "id": 22,
                "isUseInUserfieldEnabled": "Y",
                "linkedUserFields": {"CRM_LEAD|UF_TEST": "true", "TASKS_TASK|UF_CRM_TASK": "true"},
            }
        },
    ]

    assert await task_setup_cli.ensure_partner_task_binding(remote, apply=True)

    update_call = remote.call.await_args_list[1]
    assert update_call.args == (
        "crm.type.update",
        {
            "id": 22,
            "fields": {
                "isUseInUserfieldEnabled": "Y",
                "linkedUserFields": {"CRM_LEAD|UF_TEST": "true", "TASKS_TASK|UF_CRM_TASK": "true"},
            },
        },
    )
    assert remote.call.await_count == 3
    assert remote.call.await_args_list[2].args[0] == "crm.type.getByEntityTypeId"


@pytest.mark.asyncio
async def test_partner_task_binding_does_not_report_success_when_readback_is_unchanged():
    remote = AsyncMock()
    disabled = {"type": {"id": 22, "isUseInUserfieldEnabled": "N", "linkedUserFields": {}}}
    remote.call.side_effect = [disabled, {}, disabled]

    assert not await task_setup_cli.ensure_partner_task_binding(remote, apply=True)

    assert remote.call.await_count == 3


@pytest.mark.asyncio
async def test_removing_publication_tag_hides_task_before_applying_internal_content():
    db = _mock_db()
    partner = _partner()
    task = Task(
        id=uuid4(),
        partner_id=partner.id,
        title="Опубликованный текст",
        status="pending",
        assigned_to="partner",
        bitrix_imported=True,
        bitrix_published=True,
    )

    assert not await tasks._apply_remote_task_fields(
        db, task, _remote_task(tags=[], title="Внутренний текст после снятия тега")
    )

    assert task.bitrix_published is False
    assert task.bitrix_sync_error_code == "TASK_NOT_PUBLISHED"
    assert task.title == "Опубликованный текст"

    with patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(partner, None, None))):
        assert await tasks._apply_remote_task_fields(db, task, _remote_task(title="Повторно опубликовано"))

    assert task.bitrix_published is True
    assert task.title == "Повторно опубликовано"
    assert task.bitrix_sync_error_code is None


@pytest.mark.asyncio
async def test_ambiguous_target_hides_existing_task_without_applying_new_content():
    db = _mock_db()
    task = Task(
        id=uuid4(),
        title="Опубликованный текст",
        status="pending",
        assigned_to="partner",
        bitrix_imported=True,
        bitrix_published=True,
    )
    with patch.object(tasks, "_remote_task_target", new=AsyncMock(return_value=(None, None, "AMBIGUOUS_TASK_PARTNER"))):
        assert not await tasks._apply_remote_task_fields(db, task, _remote_task(title="Неоднозначный новый текст"))

    assert task.bitrix_published is False
    assert task.bitrix_sync_error_code == "AMBIGUOUS_TASK_PARTNER"
    assert task.title == "Опубликованный текст"


@pytest.mark.asyncio
@pytest.mark.parametrize("deadline", [datetime(2026, 10, 15, 22, 30, tzinfo=UTC), None])
async def test_queued_task_payload_uses_current_deadline_at_send_time(deadline):
    db = _mock_db()
    partner = _partner()
    task = Task(
        id=uuid4(),
        partner_id=partner.id,
        client_id=None,
        title="Обновлённая задача",
        assigned_to="partner",
        priority="high",
        due_at=deadline,
        due_date=date(2026, 10, 16) if deadline else None,
    )
    operation = BitrixOutboxOperation(
        local_entity_id=task.id,
        payload={"fields": {"TITLE": "Старое название", "DEADLINE": "2026-10-01T18:00:00+03:00"}},
    )

    async def current_entity(model, identity, **kwargs):
        return task if model is Task else partner if model is Partner else None

    db.get.side_effect = current_entity
    with (
        patch.object(tasks, "configured_responsible_id", new=AsyncMock(return_value=42)),
        patch.object(tasks, "_setting_user_id", new=AsyncMock(return_value=None)),
        patch.object(tasks, "configured_auditor_ids", new=AsyncMock(return_value=[])),
    ):
        await tasks.refresh_task_create_payload(db, operation)

    fields = operation.payload["fields"]
    assert fields["TITLE"] == "Обновлённая задача"
    if deadline:
        assert datetime.fromisoformat(fields["DEADLINE"]) == deadline
    else:
        assert not fields.get("DEADLINE")
    assert db.get.await_args_list[0].kwargs == {"with_for_update": True, "populate_existing": True}
