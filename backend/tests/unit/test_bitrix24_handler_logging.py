"""Authorized webhook receipts remain successful with the real structured logger."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import bitrix24_integration as integration
from app.integrations.bitrix24.tasks import TASK_ADD_EVENT
from app.models.bitrix_sync import BitrixInboundEvent


@pytest.fixture(autouse=True)
def setup_db():
    """These handler tests mock persistence and need no PostgreSQL connection."""
    yield


def _authorized_webhook():
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = SimpleNamespace(application_token_encrypted=b"test-only-token")
    payload = {
        "event": TASK_ADD_EVENT,
        "auth": {"member_id": "test-logging-member", "application_token": "test-only-application-token"},
        "data": {"FIELDS_AFTER": {"ID": "777"}},
    }
    request = MagicMock(spec=Request)
    return request, db, payload


async def test_duplicate_receipt_returns_ok_with_real_structured_logger(capsys):
    request, db, payload = _authorized_webhook()
    event_id = uuid4()
    # Keep integration.logger real: passing event= beside the positional log
    # event used to raise TypeError after the webhook receipt was committed.
    with (
        patch.object(integration, "_request_payload", new=AsyncMock(return_value=payload)),
        patch.object(integration, "decrypt_token", new=AsyncMock(return_value="test-only-application-token")),
        patch.object(integration, "register_inbound_event", new=AsyncMock(return_value=(event_id, False))) as register,
        patch.object(integration, "mark_remote_partner_conflict", new_callable=AsyncMock) as conflict,
        patch.object(integration, "process_task_status_event", new_callable=AsyncMock) as process_task,
    ):
        response = await integration.bitrix24_handler(request, db)
    assert response == {
        "ok": True,
        "duplicate": True,
        "conflict": False,
        "task_status_synced": False,
        "task_imported": False,
        "client_imported": False,
        "document_imported": False,
    }
    register.assert_awaited_once_with(db, member_id="test-logging-member", payload=payload)
    conflict.assert_not_awaited()
    process_task.assert_not_awaited()
    db.get.assert_not_awaited()
    db.commit.assert_not_awaited()
    output = capsys.readouterr().out
    assert "bitrix_event_received" in output and "bitrix_event" in output and TASK_ADD_EVENT in output


async def test_fresh_task_receipt_commits_and_returns_ok_with_real_logger(capsys):
    request, db, payload = _authorized_webhook()
    event_id = uuid4()
    receipt = BitrixInboundEvent(
        id=event_id,
        member_id="test-logging-member",
        event_key="test-logging-event-key",
        event_name=TASK_ADD_EVENT,
        remote_entity_type="task",
        remote_entity_id="777",
        payload_hash="test-payload-hash",
        status="received",
    )
    db.get.return_value = receipt

    async def complete_task_event(session, received):
        assert session is db and received is receipt
        received.status = "completed"
        return True

    with (
        patch.object(integration, "_request_payload", new=AsyncMock(return_value=payload)),
        patch.object(integration, "decrypt_token", new=AsyncMock(return_value="test-only-application-token")),
        patch.object(integration, "register_inbound_event", new=AsyncMock(return_value=(event_id, True))),
        patch.object(integration, "mark_remote_partner_conflict", new=AsyncMock(return_value=False)),
        patch.object(
            integration, "process_task_status_event", new=AsyncMock(side_effect=complete_task_event)
        ) as process,
    ):
        response = await integration.bitrix24_handler(request, db)
    assert response["ok"] is True and response["duplicate"] is False
    assert response["task_status_synced"] is True and response["task_imported"] is True
    process.assert_awaited_once_with(db, receipt)
    db.commit.assert_awaited_once()
    output = capsys.readouterr().out
    assert "bitrix_event_received" in output and TASK_ADD_EVENT in output
