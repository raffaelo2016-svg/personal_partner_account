from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.documents import (
    CRM_ACTIVITY_ENTITY_TYPE,
    _read_crm_activity,
    process_crm_activity_add_event,
)
from app.models.bitrix_sync import BitrixInboundEvent


@pytest.mark.asyncio
async def test_configurable_activity_uses_its_api_and_is_not_a_document():
    remote = AsyncMock()
    remote.call.side_effect = [
        [{"ID": "115390", "PROVIDER_ID": "CONFIGURABLE_REST_APP"}],
        {"activity": {"id": 115390, "ownerTypeId": 2, "ownerId": 456, "layout": {}}},
    ]
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(client_endpoint="https://bitrix.example/rest/")
    receipt = BitrixInboundEvent(
        member_id="member",
        event_key=uuid4().hex,
        payload_hash=uuid4().hex,
        event_name="ONCRMACTIVITYADD",
        remote_entity_type=CRM_ACTIVITY_ENTITY_TYPE,
        remote_entity_id="115390",
        status="failed",
        error_code="HTTP_400",
        attempts=4,
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
    assert receipt.attempts == 5
    assert [call.args[0] for call in remote.call.await_args_list] == [
        "crm.activity.list",
        "crm.activity.configurable.get",
    ]
    client_lookup.assert_not_awaited()
    importer.assert_not_awaited()


@pytest.mark.asyncio
async def test_standard_activity_keeps_document_attachments():
    remote = AsyncMock()
    activity = {"ID": "91", "OWNER_TYPE_ID": "2", "OWNER_ID": "456", "STORAGE_ELEMENT_IDS": [701]}
    remote.call.side_effect = [[{"ID": "91", "PROVIDER_ID": "CRM_TODO"}], activity]
    assert await _read_crm_activity(remote, "91") == activity
    remote.call.assert_awaited_with("crm.activity.get", {"id": "91"})


@pytest.mark.parametrize("response", [None, {}, [], [{"ID": "999"}], [None]])
@pytest.mark.asyncio
async def test_invalid_provider_lookup_is_not_silently_ignored(response):
    remote = AsyncMock()
    remote.call.return_value = response
    with pytest.raises(Bitrix24Error, match="INVALID_ACTIVITY_RESPONSE"):
        await _read_crm_activity(remote, "91")
    assert remote.call.await_count == 1


@pytest.mark.parametrize("response", [None, {}, {"activity": {}}, {"activity": {"id": 999}}])
@pytest.mark.asyncio
async def test_invalid_configurable_response_is_not_silently_ignored(response):
    remote = AsyncMock()
    remote.call.side_effect = [[{"ID": "91", "PROVIDER_ID": "CONFIGURABLE_REST_APP"}], response]
    with pytest.raises(Bitrix24Error, match="INVALID_ACTIVITY_RESPONSE"):
        await _read_crm_activity(remote, "91")


@pytest.mark.asyncio
async def test_real_access_error_still_fails_the_receipt():
    remote = AsyncMock()
    remote.call.side_effect = Bitrix24Error("ACCESS_DENIED", "Access denied")
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(client_endpoint="https://bitrix.example/rest/")
    receipt = BitrixInboundEvent(
        member_id="member",
        event_key=uuid4().hex,
        payload_hash=uuid4().hex,
        event_name="ONCRMACTIVITYADD",
        remote_entity_type=CRM_ACTIVITY_ENTITY_TYPE,
        remote_entity_id="91",
        attempts=0,
    )
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.documents._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.documents.Bitrix24Client", return_value=context),
    ):
        assert await process_crm_activity_add_event(db, receipt) is False
    assert receipt.status == "failed"
    assert receipt.error_code == "ACCESS_DENIED"
    assert receipt.attempts == 1
