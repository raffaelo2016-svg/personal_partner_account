from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.sync import (
    _safe_result_reference,
    enqueue_outbox_operation,
    event_fingerprint,
    is_self_originated_event,
    is_transient_error,
    register_inbound_event,
    retry_delay_seconds,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixInboundEvent, BitrixOutboxOperation


def test_event_fingerprint_does_not_depend_on_credentials():
    first = {
        "event": "ONCRMDEALUPDATE",
        "event_ts": "123",
        "data": {"FIELDS": {"ID": "42"}},
        "auth": {"application_token": "first-secret"},
    }
    second = {
        "event": "ONCRMDEALUPDATE",
        "event_ts": "123",
        "data": {"FIELDS": {"ID": "42"}},
        "auth": {"application_token": "rotated-secret"},
    }

    assert event_fingerprint(first) == event_fingerprint(second)


def test_event_fingerprint_changes_for_a_different_object():
    first = {"event": "ONCRMDEALUPDATE", "data": {"FIELDS": {"ID": "42"}}}
    second = {"event": "ONCRMDEALUPDATE", "data": {"FIELDS": {"ID": "43"}}}

    assert event_fingerprint(first) != event_fingerprint(second)


@pytest.mark.parametrize("field_name", ["ORIGINATOR_ID", "originatorId"])
def test_self_originated_event_is_detected(field_name: str):
    payload = {"data": {"FIELDS": {field_name: "partner_cabinet"}}}

    assert is_self_originated_event(payload) is True


def test_external_event_is_not_marked_as_self_originated():
    payload = {"data": {"FIELDS": {"ORIGINATOR_ID": "another-system"}}}

    assert is_self_originated_event(payload) is False


def test_retry_delay_uses_exponential_backoff(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "BITRIX_RETRY_BASE_SECONDS", 10)
    monkeypatch.setattr(settings, "BITRIX_RETRY_MAX_SECONDS", 35)

    assert retry_delay_seconds(1) == 10
    assert retry_delay_seconds(2) == 20
    assert retry_delay_seconds(3) == 35
    assert retry_delay_seconds(10) == 35


@pytest.mark.parametrize(
    ("code", "status_code", "expected"),
    [
        ("TIMEOUT", None, True),
        ("QUERY_LIMIT_EXCEEDED", 400, True),
        ("HTTP_503", 503, True),
        ("ERROR_ARGUMENT", 400, False),
    ],
)
def test_transient_error_classification(code: str, status_code: int | None, expected: bool):
    assert is_transient_error(Bitrix24Error(code, "safe", status_code=status_code)) is expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (123, "123"),
        ({"id": 456}, "456"),
        ({"ID": "789"}, "789"),
        ({"task": {"id": 12}}, "12"),
        ({"item": {"id": 34}}, "34"),
        ({"messageId": 56}, "56"),
        ({"items": [{"name": "personal data"}]}, None),
    ],
)
def test_safe_result_reference_only_extracts_ids(result, expected: str | None):
    assert _safe_result_reference(result) == expected


def test_outbox_model_defaults_are_safe():
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key="partner:1:create:v1",
        local_entity_type="partner",
        local_entity_id=uuid4(),
        bitrix_method="crm.item.add",
        payload={"entityTypeId": 1070},
    )

    assert operation.payload == {"entityTypeId": 1070}
    assert "secret" not in repr(operation)


async def _installation(db_session: AsyncSession, member_id: str = "member") -> None:
    db_session.add(
        BitrixInstallation(
            member_id=member_id,
            portal_domain="example.bitrix24.ru",
            client_endpoint="https://example.bitrix24.ru/rest/",
            server_endpoint="https://oauth.bitrix.info/rest/",
            access_token_encrypted=b"encrypted-access",
            refresh_token_encrypted=b"encrypted-refresh",
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_inbound_event_is_persisted_once(db_session: AsyncSession):
    await _installation(db_session)
    payload = {"event": "ONCRMDEALUPDATE", "event_id": "evt-1", "data": {"FIELDS": {"ID": "42"}}}

    first_id, first_created = await register_inbound_event(db_session, member_id="member", payload=payload)
    second_id, second_created = await register_inbound_event(db_session, member_id="member", payload=payload)

    count = await db_session.scalar(select(func.count(BitrixInboundEvent.id)))
    assert first_id is not None
    assert first_created is True
    assert second_id is None
    assert second_created is False
    assert count == 1


@pytest.mark.asyncio
async def test_deal_add_receipt_is_routed_to_client_import(db_session: AsyncSession):
    await _installation(db_session)
    payload = {"event": "ONCRMDEALADD", "event_id": "evt-deal-42", "data": {"FIELDS": {"ID": "42"}}}

    event_id, created = await register_inbound_event(db_session, member_id="member", payload=payload)

    receipt = await db_session.get(BitrixInboundEvent, event_id)
    assert created is True
    assert receipt is not None
    assert receipt.remote_entity_type == "client_deal"
    assert receipt.remote_entity_id == "42"


@pytest.mark.asyncio
async def test_timeline_comment_receipt_is_routed_to_document_import(db_session: AsyncSession):
    await _installation(db_session)
    payload = {
        "event": "ONCRMTIMELINECOMMENTADD",
        "event_id": "evt-comment-90",
        "data": {"ID": "90"},
    }

    event_id, created = await register_inbound_event(db_session, member_id="member", payload=payload)

    receipt = await db_session.get(BitrixInboundEvent, event_id)
    assert created is True
    assert receipt is not None
    assert receipt.remote_entity_type == "timeline_comment"
    assert receipt.remote_entity_id == "90"


@pytest.mark.asyncio
async def test_crm_activity_receipt_is_routed_to_document_import(db_session: AsyncSession):
    await _installation(db_session)
    payload = {
        "event": "ONCRMACTIVITYADD",
        "event_id": "evt-activity-91",
        "data": {"FIELDS": {"ID": "91"}},
    }

    event_id, created = await register_inbound_event(db_session, member_id="member", payload=payload)

    receipt = await db_session.get(BitrixInboundEvent, event_id)
    assert created is True
    assert receipt is not None
    assert receipt.remote_entity_type == "crm_activity"
    assert receipt.remote_entity_id == "91"


@pytest.mark.asyncio
async def test_task_add_receipt_is_routed_to_task_import(db_session: AsyncSession):
    await _installation(db_session)
    payload = {
        "event": "ONTASKADD",
        "event_id": "evt-task-92",
        "data": {"FIELDS_AFTER": {"ID": "92"}},
    }

    event_id, created = await register_inbound_event(db_session, member_id="member", payload=payload)

    receipt = await db_session.get(BitrixInboundEvent, event_id)
    assert created is True
    assert receipt is not None
    assert receipt.remote_entity_type == "task"
    assert receipt.remote_entity_id == "92"


@pytest.mark.asyncio
async def test_outbox_operation_is_enqueued_once(db_session: AsyncSession):
    await _installation(db_session)
    local_id = uuid4()
    arguments = {
        "member_id": "member",
        "operation_key": "partner:1:create:v1",
        "local_entity_type": "partner",
        "local_entity_id": local_id,
        "bitrix_method": "crm.item.add",
        "payload": {"entityTypeId": 1070},
    }

    first_id, first_created = await enqueue_outbox_operation(db_session, **arguments)
    second_id, second_created = await enqueue_outbox_operation(db_session, **arguments)

    count = await db_session.scalar(select(func.count(BitrixOutboxOperation.id)))
    assert first_id is not None
    assert first_created is True
    assert second_id is None
    assert second_created is False
    assert count == 1


async def test_unsupported_event_is_journaled_as_ignored(db_session):
    await _installation(db_session)
    receipt_id, created = await register_inbound_event(
        db_session, member_id="member", payload={"event": "UNSUPPORTED_EVENT", "event_id": "unsupported"}
    )
    assert created
    receipt = await db_session.get(BitrixInboundEvent, receipt_id)
    assert receipt.status == "ignored"
    assert receipt.remote_entity_type is None
