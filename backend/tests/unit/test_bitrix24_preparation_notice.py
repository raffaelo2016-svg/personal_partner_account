from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.preparation_notice import (
    PREPARATION_NOTICE_COMMENT,
    PREPARATION_NOTICE_ENTITY_TYPE,
    execute_preparation_notice,
    schedule_preparation_notice,
)
from app.integrations.bitrix24.sync import _complete_client_projection, _execute_operation
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.client import Client


def operation():
    return BitrixOutboxOperation(
        local_entity_type=PREPARATION_NOTICE_ENTITY_TYPE,
        bitrix_method="crm.timeline.comment.add",
        payload={
            "fields": {
                "ENTITY_ID": "42",
                "ENTITY_TYPE": "deal",
                "COMMENT": PREPARATION_NOTICE_COMMENT,
            }
        },
    )


@pytest.mark.parametrize(
    "mode,category,stage,expected",
    [
        ("partner", settings.BITRIX_SUPPORT_DEAL_CATEGORY_ID, settings.BITRIX_SUPPORT_DEAL_STAGE_ID, True),
        ("uritech", settings.BITRIX_SUPPORT_DEAL_CATEGORY_ID, settings.BITRIX_SUPPORT_DEAL_STAGE_ID, False),
        ("partner", settings.BITRIX_DEAL_CATEGORY_ID, settings.BITRIX_SUPPORT_DEAL_STAGE_ID, False),
        ("partner", settings.BITRIX_SUPPORT_DEAL_CATEGORY_ID, "C7:NEW", False),
    ],
)
async def test_notice_only_for_partner_preparation_in_support_partner_stage(mode, category, stage, expected):
    db = AsyncMock()
    client = Client(id=uuid4(), document_preparation_mode=mode)
    await schedule_preparation_notice(
        db,
        client=client,
        member_id="portal",
        deal_id="42",
        category_id=category,
        stage_id=stage,
    )
    assert db.execute.await_count == int(expected)
    if expected:
        statement = db.execute.await_args.args[0].compile(dialect=postgresql.dialect())
        assert "ON CONFLICT ON CONSTRAINT uq_bitrix_outbox_operation_key DO NOTHING" in str(statement)
        assert statement.params["payload"]["fields"]["COMMENT"] == (
            "[B][COLOR=#FF0000]Партнер сам готовит документы для подачи в суд.[/COLOR][/B]"
        )


async def test_worker_creates_formatted_timeline_comment():
    remote = AsyncMock()
    remote.list_all.return_value = []
    remote.call.return_value = 99
    op = operation()
    assert await _execute_operation(remote, op) == "99"
    remote.call.assert_awaited_once_with("crm.timeline.comment.add", op.payload)


async def test_retry_recovers_existing_comment_without_duplicate():
    remote = AsyncMock()
    remote.list_all.return_value = [{"ID": "99", "COMMENT": PREPARATION_NOTICE_COMMENT}]
    assert await execute_preparation_notice(remote, operation()) == "99"
    remote.call.assert_not_awaited()
    assert remote.list_all.await_args.args[1]["filter"] == {"ENTITY_ID": "42", "ENTITY_TYPE": "deal"}


async def test_comment_error_remains_retryable_by_outbox():
    remote = AsyncMock()
    remote.list_all.return_value = []
    remote.call.side_effect = Bitrix24Error("TIMEOUT", "timeout")
    with pytest.raises(Bitrix24Error, match="timeout"):
        await execute_preparation_notice(remote, operation())


async def test_comment_missing_id_is_reported_as_failure():
    remote = AsyncMock()
    remote.list_all.return_value = []
    remote.call.return_value = None
    with pytest.raises(Bitrix24Error):
        await execute_preparation_notice(remote, operation())


async def test_deal_completion_queues_notice_with_created_deal_id():
    client = Client(id=uuid4(), document_preparation_mode="partner")
    db = AsyncMock()
    db.get.return_value = client
    db.scalars.return_value = MagicMock()
    db.scalars.return_value.all.return_value = []
    op = BitrixOutboxOperation(
        local_entity_type="client_deal",
        local_entity_id=client.id,
        member_id="portal",
        result_reference="42",
        payload={
            "fields": {
                "CATEGORY_ID": settings.BITRIX_SUPPORT_DEAL_CATEGORY_ID,
                "STAGE_ID": settings.BITRIX_SUPPORT_DEAL_STAGE_ID,
            }
        },
    )
    with patch("app.integrations.bitrix24.sync.schedule_preparation_notice", new_callable=AsyncMock) as schedule:
        await _complete_client_projection(db, op)
    schedule.assert_awaited_once_with(
        db,
        client=client,
        member_id="portal",
        deal_id="42",
        category_id=settings.BITRIX_SUPPORT_DEAL_CATEGORY_ID,
        stage_id=settings.BITRIX_SUPPORT_DEAL_STAGE_ID,
    )
    assert client.bitrix_deal_id == "42"
