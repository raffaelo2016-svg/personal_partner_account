from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client_setup_cli import ENTITY_ID, FIELD_DEFINITIONS, _provision_field
from app.integrations.bitrix24.clients import (
    CLIENT_CONTACT_ENTITY_TYPE,
    CLIENT_DEAL_CATEGORY_ID,
    CLIENT_DEAL_FIELDS,
    CLIENT_DEAL_STAGE_ID,
    build_client_contact_payload,
    build_client_deal_payload,
    schedule_client_creation,
)
from app.integrations.bitrix24.sync import _execute_operation
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixOutboxOperation
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


def test_deal_payload_links_contact_and_partner_without_changing_workflow():
    client = _client()

    payload = build_client_deal_payload(client, "321", "654")["fields"]

    assert payload["CATEGORY_ID"] == CLIENT_DEAL_CATEGORY_ID == 3
    assert payload["STAGE_ID"] == CLIENT_DEAL_STAGE_ID == "C3:NEW"
    assert payload["CONTACT_ID"] == "654"
    assert payload[f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}"] == "321"
    assert payload[CLIENT_DEAL_FIELDS["case_number"]] == client.case_number


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
