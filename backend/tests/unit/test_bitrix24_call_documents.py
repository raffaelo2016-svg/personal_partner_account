from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.integrations.bitrix24.documents import (
    CRM_ACTIVITY_ENTITY_TYPE,
    _is_call_activity,
    process_crm_activity_add_event,
)
from app.models.bitrix_sync import BitrixInboundEvent


@pytest.mark.parametrize(
    "activity",
    [
        {"TYPE_ID": "2", "PROVIDER_ID": "VOXIMPLANT_CALL"},
        {"TYPE_ID": 2},
        {"PROVIDER_ID": "VOXIMPLANT_CALL"},
        {"typeId": 2, "providerId": "VOXIMPLANT_CALL"},
    ],
)
def test_recognizes_call_activity(activity):
    assert _is_call_activity(activity)


@pytest.mark.parametrize(
    "activity",
    [
        {},
        {"TYPE_ID": "4", "PROVIDER_ID": "CRM_EMAIL"},
        {"TYPE_ID": "6", "PROVIDER_ID": "CRM_TODO", "STORAGE_ELEMENT_IDS": [701]},
    ],
)
def test_other_activities_can_still_import_attachments(activity):
    assert not _is_call_activity(activity)


@pytest.mark.asyncio
async def test_call_recording_is_ignored_without_reading_or_importing_its_file():
    remote = AsyncMock()
    remote.call.side_effect = [
        [{"ID": "91", "PROVIDER_ID": "VOXIMPLANT_CALL"}],
        {
            "ID": "91",
            "TYPE_ID": "2",
            "PROVIDER_ID": "VOXIMPLANT_CALL",
            "OWNER_TYPE_ID": "2",
            "OWNER_ID": "456",
            "STORAGE_ELEMENT_IDS": [701],
        },
    ]
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(client_endpoint="https://bitrix.example/rest/")
    receipt = BitrixInboundEvent(
        member_id="member",
        event_key=uuid4().hex,
        payload_hash=uuid4().hex,
        event_name="ONCRMACTIVITYADD",
        remote_entity_type=CRM_ACTIVITY_ENTITY_TYPE,
        remote_entity_id="91",
        status="failed",
        error_code="UNSUPPORTED_FILE_TYPE",
        attempts=7,
    )
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.documents._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.documents.Bitrix24Client", return_value=context),
        patch("app.integrations.bitrix24.documents._local_client_for_deal", new=AsyncMock()) as client_lookup,
        patch("app.integrations.bitrix24.documents._import_remote_files", new=AsyncMock()) as importer,
    ):
        assert await process_crm_activity_add_event(db, receipt) is True

    assert receipt.status == "ignored"
    assert receipt.error_code is None
    assert receipt.processed_at is not None
    assert receipt.attempts == 8
    assert [call.args[0] for call in remote.call.await_args_list] == ["crm.activity.list", "crm.activity.get"]
    client_lookup.assert_not_awaited()
    importer.assert_not_awaited()


@pytest.mark.asyncio
async def test_manually_attached_mp3_in_non_call_activity_is_still_imported():
    remote = AsyncMock()
    remote.call.side_effect = [
        [{"ID": "92", "PROVIDER_ID": "CRM_TODO"}],
        {
            "ID": "92",
            "TYPE_ID": "6",
            "PROVIDER_ID": "CRM_TODO",
            "OWNER_TYPE_ID": "2",
            "OWNER_ID": "456",
            "FILES": [{"ID": "702", "name": "explanation.mp3"}],
        },
    ]
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(client_endpoint="https://bitrix.example/rest/")
    receipt = BitrixInboundEvent(
        member_id="member",
        event_key=uuid4().hex,
        payload_hash=uuid4().hex,
        event_name="ONCRMACTIVITYADD",
        remote_entity_type=CRM_ACTIVITY_ENTITY_TYPE,
        remote_entity_id="92",
        status="received",
        attempts=0,
    )
    local_client = SimpleNamespace(id=uuid4())
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.documents._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.documents.Bitrix24Client", return_value=context),
        patch(
            "app.integrations.bitrix24.documents._local_client_for_deal",
            new=AsyncMock(return_value=local_client),
        ),
        patch(
            "app.integrations.bitrix24.documents._import_remote_files", new=AsyncMock(return_value=True)
        ) as importer,
    ):
        assert await process_crm_activity_add_event(db, receipt) is True

    assert receipt.status == "completed"
    assert receipt.error_code is None
    importer.assert_awaited_once()
    assert importer.await_args.kwargs["files"] == [{"ID": "702", "name": "explanation.mp3"}]
