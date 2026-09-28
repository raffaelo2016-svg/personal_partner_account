from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Error
from app.integrations.bitrix24.client_setup_cli import ENTITY_ID, FIELD_DEFINITIONS, _provision_field
from app.integrations.bitrix24.clients import (
    CLIENT_CONTACT_ENTITY_TYPE,
    CLIENT_DEAL_CATEGORY_ID,
    CLIENT_DEAL_FIELDS,
    CLIENT_DEAL_STAGE_ID,
    CLIENT_DEAL_UPDATE_EVENT,
    CLIENT_SUPPORT_DEAL_CATEGORY_ID,
    CLIENT_SUPPORT_DEAL_STAGE_ID,
    build_client_contact_payload,
    build_client_deal_payload,
    extract_client_deal_event_reference,
    process_client_deal_add_event,
    schedule_client_creation,
)
from app.integrations.bitrix24.sync import _execute_operation
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.partner import Partner
from app.models.user import User


def _client(partner_id=None) -> Client:
    return Client(
        id=uuid4(),
        partner_id=partner_id or uuid4(),
        type="before_court",
        status="documents_collection",
        full_name="Иванов Иван Иванович",
        date_of_birth=date(1980, 1, 2),
        passport_series="4500",
        passport_number="123456",
        inn="770123456789",
        snils="12345678901",
        registration_address="Секретный адрес",
        phone="+79990000000",
        email="client@example.test",
        region="Москва",
        arbitrage_court="Арбитражный суд Москвы",
        case_number="А40-1/2026",
    )


def test_contact_payload_excludes_sensitive_identity_data():
    client = _client()

    payload = build_client_contact_payload(client)
    serialized = str(payload)

    assert payload["fields"]["LAST_NAME"] == "Иванов"
    assert payload["fields"]["NAME"] == "Иван"
    assert payload["fields"]["SECOND_NAME"] == "Иванович"
    assert payload["fields"]["ORIGIN_ID"] == str(client.id)
    assert "4500" not in serialized
    assert "123456" not in serialized
    assert client.inn not in serialized
    assert client.snils not in serialized
    assert client.registration_address not in serialized


def test_before_court_deal_routes_to_support_department():
    client = _client()

    payload = build_client_deal_payload(client, "321", "654")["fields"]

    assert payload["CATEGORY_ID"] == CLIENT_SUPPORT_DEAL_CATEGORY_ID == 7
    assert payload["STAGE_ID"] == CLIENT_SUPPORT_DEAL_STAGE_ID == "C7:NEW"
    assert payload["CONTACT_ID"] == "654"
    assert payload[f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}"] == "321"
    assert payload[CLIENT_DEAL_FIELDS["case_number"]] == client.case_number


def test_in_court_deal_routes_to_arbitration():
    client = _client()
    client.type = "in_court"

    payload = build_client_deal_payload(client, "321", "654")["fields"]

    assert payload["CATEGORY_ID"] == CLIENT_DEAL_CATEGORY_ID == 3
    assert payload["STAGE_ID"] == CLIENT_DEAL_STAGE_ID == "C3:NEW"


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"FIELDS": {"ID": "42"}}},
        {"data[FIELDS][ID]": "42"},
    ],
)
def test_client_deal_event_reference_supports_json_and_form_payloads(payload):
    assert extract_client_deal_event_reference("ONCRMDEALADD", payload) == "42"
    assert extract_client_deal_event_reference(CLIENT_DEAL_UPDATE_EVENT, payload) == "42"
    assert extract_client_deal_event_reference("ONCRMDEALDELETE", payload) is None


@pytest.mark.asyncio
async def test_client_field_setup_uses_deal_entity_and_full_name():
    remote = AsyncMock()

    await _provision_field(remote, FIELD_DEFINITIONS[0])

    params = remote.call.await_args.args[1]
    assert params["field"]["entityId"] == ENTITY_ID == "CRM_DEAL"
    assert params["field"]["fieldName"] == CLIENT_DEAL_FIELDS["region"]


async def _saved_entities(db: AsyncSession, *, partner_synced: bool = True) -> tuple[Partner, Client]:
    installation = BitrixInstallation(
        member_id="member-stage-4",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"encrypted-access",
        refresh_token_encrypted=b"encrypted-refresh",
        status="L",
    )
    user = User(email="stage4@example.test", hashed_password="hash", role="partner", is_active=True)
    db.add_all([installation, user])
    await db.flush()
    partner = Partner(
        user_id=user.id,
        partner_type="legal",
        company_name="ООО Тест",
        director_name="Петров Пётр Петрович",
        inn="7701234567",
        phone="+79990000001",
        status="active",
        bitrix_partner_item_id="321" if partner_synced else None,
        bitrix_sync_status="synced" if partner_synced else "pending",
    )
    db.add(partner)
    await db.flush()
    client = _client(partner.id)
    db.add(client)
    await db.flush()
    return partner, client


@pytest.mark.asyncio
async def test_client_contact_is_queued_once(db_session: AsyncSession):
    partner, client = await _saved_entities(db_session)

    first = await schedule_client_creation(db_session, client, partner=partner)
    second = await schedule_client_creation(db_session, client, partner=partner)

    count = await db_session.scalar(select(func.count(BitrixOutboxOperation.id)))
    operation = await db_session.scalar(select(BitrixOutboxOperation))
    assert first is True
    assert second is False
    assert count == 1
    assert operation is not None
    assert operation.local_entity_type == CLIENT_CONTACT_ENTITY_TYPE
    assert client.bitrix_sync_status == "pending"


@pytest.mark.asyncio
async def test_client_waits_for_partner_without_creating_operation(db_session: AsyncSession):
    partner, client = await _saved_entities(db_session, partner_synced=False)

    queued = await schedule_client_creation(db_session, client, partner=partner)

    count = await db_session.scalar(select(func.count(BitrixOutboxOperation.id)))
    assert queued is False
    assert count == 0
    assert client.bitrix_sync_status == "pending"
    assert client.bitrix_sync_error_code == "PARTNER_NOT_SYNCED"


@pytest.mark.asyncio
async def test_create_recovers_existing_remote_contact_before_retrying_add():
    local_id = uuid4()
    operation = BitrixOutboxOperation(
        member_id="member",
        operation_key=f"client:contact:{local_id}:v1",
        local_entity_type=CLIENT_CONTACT_ENTITY_TYPE,
        local_entity_id=local_id,
        bitrix_method="crm.contact.add",
        payload={"fields": {"ORIGINATOR_ID": "partner_cabinet", "ORIGIN_ID": str(local_id)}},
    )
    remote = AsyncMock()
    remote.call.return_value = [{"ID": "777"}]

    result = await _execute_operation(remote, operation)

    assert result == "777"
    remote.call.assert_awaited_once()
    assert remote.call.await_args.args[0] == "crm.contact.list"


@pytest.mark.asyncio
async def test_external_support_deal_creates_linked_client(db_session: AsyncSession):
    partner, _ = await _saved_entities(db_session)
    db_session.add(
        BitrixEntityMap(
            member_id="member-stage-4",
            local_entity_type="partner_smart_process",
            local_entity_id=partner.id,
            bitrix_entity_type=f"crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}",
            bitrix_entity_id="321",
        )
    )
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name="ONCRMDEALADD",
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="900",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.side_effect = [
        {
            "ID": "900",
            "CATEGORY_ID": "7",
            "CONTACT_ID": "901",
            f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}": "321",
            CLIENT_DEAL_FIELDS["client_type"]: "before_court",
            CLIENT_DEAL_FIELDS["client_status"]: "documents_collection",
            CLIENT_DEAL_FIELDS["region"]: "Москва",
            CLIENT_DEAL_FIELDS["case_number"]: "А40-1/2026",
        },
        {
            "ID": "901",
            "LAST_NAME": "Иванов",
            "NAME": "Иван",
            "SECOND_NAME": "Иванович",
            "BIRTHDATE": "1980-01-02",
            "PHONE": [{"VALUE": "+79990000000"}],
            "EMAIL": [{"VALUE": "client@example.test"}],
        },
    ]
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
        patch(
            "app.services.finance_service.create_court_fee_for_client",
            new=AsyncMock(return_value=None),
        ),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    imported = await db_session.scalar(select(Client).where(Client.bitrix_deal_id == "900"))
    assert imported is not None
    mapping_count = await db_session.scalar(
        select(func.count(BitrixEntityMap.id)).where(BitrixEntityMap.local_entity_id == imported.id)
    )
    assert completed is True
    assert imported.partner_id == partner.id
    assert imported.full_name == "Иванов Иван Иванович"
    assert imported.bitrix_contact_id == "901"
    assert imported.bitrix_sync_status == "synced"
    assert mapping_count == 2
    assert receipt.status == "completed"


@pytest.mark.asyncio
async def test_deal_update_imports_client_and_resolves_old_partner_warning(db_session: AsyncSession):
    partner, _ = await _saved_entities(db_session)
    db_session.add(
        BitrixEntityMap(
            member_id="member-stage-4",
            local_entity_type="partner_smart_process",
            local_entity_id=partner.id,
            bitrix_entity_type=f"crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}",
            bitrix_entity_id="321",
        )
    )
    old_receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name="ONCRMDEALADD",
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="905",
        status="failed",
        error_code="PARTNER_NOT_LINKED",
        attempts=1,
    )
    update_receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name=CLIENT_DEAL_UPDATE_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="905",
    )
    db_session.add_all([old_receipt, update_receipt])
    await db_session.flush()

    remote = AsyncMock()
    remote.call.side_effect = [
        {
            "ID": "905",
            "CATEGORY_ID": "3",
            "CONTACT_ID": "906",
            f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}": "321",
            CLIENT_DEAL_FIELDS["client_type"]: "before_court",
            CLIENT_DEAL_FIELDS["client_status"]: "documents_collection",
        },
        {
            "ID": "906",
            "LAST_NAME": "Новый",
            "NAME": "Клиент",
        },
    ]
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
        patch("app.services.finance_service.create_court_fee_for_client", new=AsyncMock(return_value=None)),
    ):
        completed = await process_client_deal_add_event(db_session, update_receipt)

    imported = await db_session.scalar(select(Client).where(Client.bitrix_deal_id == "905"))
    await db_session.refresh(old_receipt)
    assert completed is True
    assert imported is not None
    assert imported.partner_id == partner.id
    assert update_receipt.status == "completed"
    assert old_receipt.status == "ignored"
    assert old_receipt.error_code is None


@pytest.mark.asyncio
async def test_deal_update_moves_existing_client_to_selected_partner(db_session: AsyncSession):
    old_partner, existing_client = await _saved_entities(db_session)
    second_user = User(email="second-partner@example.test", hashed_password="hash", role="partner", is_active=True)
    db_session.add(second_user)
    await db_session.flush()
    new_partner = Partner(
        user_id=second_user.id,
        partner_type="legal",
        company_name="ООО Новый партнёр",
        director_name="Новый Партнёр",
        inn="7701234568",
        phone="+79990000002",
        status="active",
        bitrix_partner_item_id="654",
        bitrix_sync_status="synced",
    )
    db_session.add(new_partner)
    await db_session.flush()
    db_session.add_all(
        [
            BitrixEntityMap(
                member_id="member-stage-4",
                local_entity_type="client_deal",
                local_entity_id=existing_client.id,
                bitrix_entity_type="crm_deal",
                bitrix_entity_id="907",
            ),
            BitrixEntityMap(
                member_id="member-stage-4",
                local_entity_type="partner_smart_process",
                local_entity_id=new_partner.id,
                bitrix_entity_type=f"crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}",
                bitrix_entity_id="654",
            ),
        ]
    )
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name=CLIENT_DEAL_UPDATE_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="907",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {
        "ID": "907",
        "CATEGORY_ID": "3",
        "ORIGINATOR_ID": "partner_cabinet",
        f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}": "654",
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    await db_session.refresh(existing_client)
    assert completed is True
    assert existing_client.partner_id != old_partner.id
    assert existing_client.partner_id == new_partner.id
    assert receipt.status == "completed"


@pytest.mark.asyncio
async def test_removing_partner_from_existing_deal_returns_it_to_attention(db_session: AsyncSession):
    partner, existing_client = await _saved_entities(db_session)
    db_session.add(
        BitrixEntityMap(
            member_id="member-stage-4",
            local_entity_type="client_deal",
            local_entity_id=existing_client.id,
            bitrix_entity_type="crm_deal",
            bitrix_entity_id="908",
        )
    )
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name=CLIENT_DEAL_UPDATE_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="908",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {"ID": "908", "CATEGORY_ID": "3"}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    assert completed is False
    assert receipt.status == "failed"
    assert receipt.error_code == "PARTNER_NOT_LINKED"
    assert existing_client.partner_id == partner.id


@pytest.mark.asyncio
async def test_unmapped_deal_update_without_partner_is_ignored(db_session: AsyncSession):
    await _saved_entities(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name=CLIENT_DEAL_UPDATE_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="909",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {"ID": "909", "CATEGORY_ID": "3"}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    assert completed is True
    assert receipt.status == "ignored"
    assert receipt.error_code is None
    assert receipt.processed_at is not None
    assert receipt.attempts == 1


@pytest.mark.asyncio
async def test_deal_moved_out_of_client_funnel_resolves_old_warning(db_session: AsyncSession):
    await _saved_entities(db_session)
    old_receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name="ONCRMDEALADD",
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="910",
        status="failed",
        error_code="PARTNER_NOT_LINKED",
        attempts=1,
    )
    update_receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name=CLIENT_DEAL_UPDATE_EVENT,
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="910",
    )
    db_session.add_all([old_receipt, update_receipt])
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {"ID": "910", "CATEGORY_ID": "18"}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, update_receipt)

    await db_session.refresh(old_receipt)
    assert completed is True
    assert update_receipt.status == "ignored"
    assert old_receipt.status == "ignored"
    assert old_receipt.error_code is None


@pytest.mark.asyncio
async def test_deleted_remote_deal_resolves_old_warning(db_session: AsyncSession):
    await _saved_entities(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name="ONCRMDEALADD",
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="911",
        status="failed",
        error_code="PARTNER_NOT_LINKED",
        attempts=1,
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.side_effect = Bitrix24Error("", "Not found", status_code=400)
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    assert completed is True
    assert receipt.status == "ignored"
    assert receipt.error_code is None
    assert receipt.processed_at is not None


@pytest.mark.asyncio
async def test_external_deal_without_partner_link_waits_silently_for_qualification(db_session: AsyncSession):
    await _saved_entities(db_session)
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name="ONCRMDEALADD",
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="902",
    )
    db_session.add(receipt)
    await db_session.flush()
    remote = AsyncMock()
    remote.call.return_value = {"ID": "902", "CATEGORY_ID": "3", "CONTACT_ID": "903"}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    assert completed is True
    assert receipt.status == "ignored"
    assert receipt.error_code is None
    assert receipt.processed_at is not None


@pytest.mark.asyncio
async def test_external_deal_does_not_reuse_contact_of_existing_client(db_session: AsyncSession):
    partner, existing_client = await _saved_entities(db_session)
    db_session.add_all(
        [
            BitrixEntityMap(
                member_id="member-stage-4",
                local_entity_type="partner_smart_process",
                local_entity_id=partner.id,
                bitrix_entity_type=f"crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}",
                bitrix_entity_id="321",
            ),
            BitrixEntityMap(
                member_id="member-stage-4",
                local_entity_type="client_contact",
                local_entity_id=existing_client.id,
                bitrix_entity_type="crm_contact",
                bitrix_entity_id="901",
            ),
        ]
    )
    receipt = BitrixInboundEvent(
        member_id="member-stage-4",
        event_key=uuid4().hex,
        event_name="ONCRMDEALADD",
        payload_hash=uuid4().hex,
        remote_entity_type="client_deal",
        remote_entity_id="904",
    )
    db_session.add(receipt)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {
        "ID": "904",
        "CATEGORY_ID": "3",
        "CONTACT_ID": "901",
        f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}": "321",
    }
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.clients._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.clients.Bitrix24Client", return_value=context),
    ):
        completed = await process_client_deal_add_event(db_session, receipt)

    assert completed is False
    assert receipt.status == "failed"
    assert receipt.error_code == "CONTACT_ALREADY_LINKED"
    assert remote.call.await_count == 1
