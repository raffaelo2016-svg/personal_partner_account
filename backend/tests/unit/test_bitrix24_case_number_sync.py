from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.clients import (
    CLIENT_DEAL_FIELDS,
    CLIENT_DEAL_UPDATE_ENTITY_TYPE,
    CLIENT_DEAL_UPDATE_METHOD,
    schedule_client_case_number_update,
)
from app.integrations.bitrix24.sync import (
    _complete_client_case_number_update,
    _execute_operation,
    refresh_client_case_number_payload,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.client import Client
from app.models.partner import Partner
from app.models.user import User
from app.schemas.client import ClientUpdate
from app.services.client_service import update_client


async def _linked_client(db: AsyncSession, *, deal_id: str | None = "900") -> Client:
    installation = BitrixInstallation(
        member_id="member-case-number",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"encrypted-access",
        refresh_token_encrypted=b"encrypted-refresh",
        status="L",
    )
    user = User(email="case-number@example.test", hashed_password="hash", role="partner", is_active=True)
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
        bitrix_partner_item_id="321",
        bitrix_sync_status="synced",
    )
    db.add(partner)
    await db.flush()
    client = Client(
        partner_id=partner.id,
        type="in_court",
        status="waiting_hearing",
        full_name="Иванов Иван Иванович",
        case_number="А40-1/2026",
        bitrix_deal_id=deal_id,
        bitrix_sync_status="synced",
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


async def _update_operations(db: AsyncSession) -> list[BitrixOutboxOperation]:
    return list(
        (
            await db.scalars(
                select(BitrixOutboxOperation).where(
                    BitrixOutboxOperation.local_entity_type == CLIENT_DEAL_UPDATE_ENTITY_TYPE
                )
            )
        ).all()
    )


@pytest.mark.asyncio
async def test_schedule_queues_case_number_update_for_linked_deal(db_session: AsyncSession):
    client = await _linked_client(db_session)

    queued = await schedule_client_case_number_update(db_session, client)

    operations = await _update_operations(db_session)
    assert queued is True
    assert len(operations) == 1
    operation = operations[0]
    assert operation.bitrix_method == CLIENT_DEAL_UPDATE_METHOD == "crm.deal.update"
    assert operation.local_entity_id == client.id
    assert operation.payload == {"deal_id": "900"}
    assert client.bitrix_sync_status == "pending"


@pytest.mark.asyncio
async def test_schedule_coalesces_pending_operations(db_session: AsyncSession):
    client = await _linked_client(db_session)

    await schedule_client_case_number_update(db_session, client)
    await schedule_client_case_number_update(db_session, client)

    assert len(await _update_operations(db_session)) == 1


@pytest.mark.asyncio
async def test_schedule_skips_client_without_linked_deal(db_session: AsyncSession):
    client = await _linked_client(db_session, deal_id=None)

    queued = await schedule_client_case_number_update(db_session, client)

    assert queued is False
    assert await _update_operations(db_session) == []


@pytest.mark.asyncio
async def test_refresh_payload_uses_current_case_number(db_session: AsyncSession):
    client = await _linked_client(db_session)
    operation = BitrixOutboxOperation(
        member_id="member-case-number",
        operation_key=f"client:deal:update:{uuid4()}",
        local_entity_type=CLIENT_DEAL_UPDATE_ENTITY_TYPE,
        local_entity_id=client.id,
        bitrix_method=CLIENT_DEAL_UPDATE_METHOD,
        payload={"deal_id": "900"},
    )
    db_session.add(operation)
    await db_session.flush()
    client.case_number = "А66-5146/2026"
    await db_session.flush()

    await refresh_client_case_number_payload(db_session, operation)

    assert operation.payload == {
        "id": "900",
        "fields": {CLIENT_DEAL_FIELDS["case_number"]: "А66-5146/2026"},
    }


@pytest.mark.asyncio
async def test_refresh_payload_clears_removed_case_number(db_session: AsyncSession):
    client = await _linked_client(db_session)
    operation = BitrixOutboxOperation(
        member_id="member-case-number",
        operation_key=f"client:deal:update:{uuid4()}",
        local_entity_type=CLIENT_DEAL_UPDATE_ENTITY_TYPE,
        local_entity_id=client.id,
        bitrix_method=CLIENT_DEAL_UPDATE_METHOD,
        payload={"deal_id": "900"},
    )
    db_session.add(operation)
    await db_session.flush()
    client.case_number = None
    await db_session.flush()

    await refresh_client_case_number_payload(db_session, operation)

    assert operation.payload["fields"][CLIENT_DEAL_FIELDS["case_number"]] == ""


@pytest.mark.asyncio
async def test_execute_sends_deal_update_client_call(db_session: AsyncSession):
    client = await _linked_client(db_session)
    operation = BitrixOutboxOperation(
        member_id="member-case-number",
        operation_key=f"client:deal:update:{uuid4()}",
        local_entity_type=CLIENT_DEAL_UPDATE_ENTITY_TYPE,
        local_entity_id=client.id,
        bitrix_method=CLIENT_DEAL_UPDATE_METHOD,
        payload={"deal_id": "900"},
    )
    db_session.add(operation)
    await db_session.flush()
    remote = AsyncMock()
    remote.call.return_value = True

    await _execute_operation(remote, operation, db=db_session)

    remote.call.assert_awaited_once_with(
        "crm.deal.update",
        {
            "id": "900",
            "fields": {CLIENT_DEAL_FIELDS["case_number"]: "А40-1/2026"},
        },
    )


@pytest.mark.asyncio
async def test_completion_marks_client_synced(db_session: AsyncSession):
    client = await _linked_client(db_session)
    operation = BitrixOutboxOperation(
        member_id="member-case-number",
        operation_key=f"client:deal:update:{uuid4()}",
        local_entity_type=CLIENT_DEAL_UPDATE_ENTITY_TYPE,
        local_entity_id=client.id,
        bitrix_method=CLIENT_DEAL_UPDATE_METHOD,
        payload={"deal_id": "900"},
    )
    db_session.add(operation)
    await db_session.flush()
    client.bitrix_sync_status = "processing"

    await _complete_client_case_number_update(db_session, operation)

    assert client.bitrix_sync_status == "synced"
    assert client.bitrix_sync_error_code is None
    assert client.bitrix_synced_at is not None


@pytest.mark.asyncio
async def test_update_client_api_schedules_case_number_sync(db_session: AsyncSession):
    client = await _linked_client(db_session)

    updated = await update_client(db_session, str(client.id), ClientUpdate(case_number="А66-5146/2026"))

    operations = await _update_operations(db_session)
    assert updated.case_number == "А66-5146/2026"
    assert len(operations) == 1
    assert operations[0].bitrix_method == CLIENT_DEAL_UPDATE_METHOD


@pytest.mark.asyncio
async def test_update_client_skips_sync_when_case_number_is_unchanged(db_session: AsyncSession):
    client = await _linked_client(db_session)

    await update_client(db_session, str(client.id), ClientUpdate(case_number="А40-1/2026"))

    assert len(await _update_operations(db_session)) == 0


@pytest.mark.asyncio
async def test_update_client_skips_sync_without_linked_deal(db_session: AsyncSession):
    client = await _linked_client(db_session, deal_id=None)

    await update_client(db_session, str(client.id), ClientUpdate(case_number="А66-5146/2026"))

    assert len(await _update_operations(db_session)) == 0
    assert await db_session.scalar(select(func.count(BitrixOutboxOperation.id))) == 0
