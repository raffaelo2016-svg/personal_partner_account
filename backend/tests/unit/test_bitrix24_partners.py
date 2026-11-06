from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.partner_setup_cli import (
    ENTITY_ID,
    FIELD_DEFINITIONS,
    _existing_field_names,
    _provision_field,
)
from app.integrations.bitrix24.partners import (
    PARTNER_ENTITY_TYPE,
    PARTNER_FIELDS,
    build_partner_create_payload,
    mark_remote_partner_conflict,
    reconcile_remote_partner_profiles,
    schedule_partner_creation,
)
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixEntityMap, BitrixOutboxOperation
from app.models.partner import Partner
from app.models.user import User


def _partner(user_id=None) -> Partner:
    return Partner(
        id=uuid4(),
        user_id=user_id or uuid4(),
        partner_type="legal",
        company_name='ООО "Партнёр"',
        director_name="Иванов Иван Иванович",
        inn="7701234567",
        kpp="770101001",
        phone="+79990000000",
        legal_address="Москва",
        court_fee_per_client=1_500_000,
        payment_term_days=10,
        status="active",
    )


def _remote_item(partner: Partner, email: str = "stage3@example.test") -> dict:
    return build_partner_create_payload(partner, email)["fields"]


def test_partner_payload_contains_required_projection_only():
    partner = _partner()

    payload = build_partner_create_payload(partner, "partner@example.test")

    assert payload["entityTypeId"] == settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID
    assert payload["useOriginalUfNames"] == "Y"
    assert payload["fields"]["xmlId"] == str(partner.id)
    assert payload["fields"][PARTNER_FIELDS["company_name"]] == partner.company_name
    assert payload["fields"][PARTNER_FIELDS["director_name"]] == partner.director_name
    assert payload["fields"][PARTNER_FIELDS["court_fee"]] == "15000.00|RUB"
    assert payload["fields"][PARTNER_FIELDS["payment_days"]] == 10
    assert "passport" not in str(payload).lower()


@pytest.mark.asyncio
async def test_partner_field_setup_uses_full_bitrix_field_name():
    client = AsyncMock()

    await _provision_field(client, FIELD_DEFINITIONS[0])

    params = client.call.await_args.args[1]
    assert params["field"]["entityId"] == ENTITY_ID == "CRM_16"
    assert params["field"]["fieldName"] == PARTNER_FIELDS["partner_type"] == "UF_CRM_16_YRITECH_PARTNER_TYPE"


@pytest.mark.asyncio
async def test_partner_field_setup_reads_fields_through_crm_item_fields():
    client = AsyncMock()
    client.call.return_value = {
        "fields": {
            "ufCrm31YritechPartnerType": {
                "upperName": PARTNER_FIELDS["partner_type"],
                "type": "string",
            }
        }
    }

    names = await _existing_field_names(client)

    assert names == {PARTNER_FIELDS["partner_type"]}
    client.call.assert_awaited_once_with(
        "crm.item.fields",
        {"entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID},
    )


async def _installation(db: AsyncSession) -> BitrixInstallation:
    installation = BitrixInstallation(
        member_id="member-stage-3",
        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
        server_endpoint="https://oauth.bitrix.info/rest/",
        access_token_encrypted=b"encrypted-access",
        refresh_token_encrypted=b"encrypted-refresh",
        status="L",
    )
    db.add(installation)
    await db.flush()
    return installation


async def _saved_partner(db: AsyncSession) -> Partner:
    user = User(email="stage3@example.test", hashed_password="hash", role="partner", is_active=True)
    db.add(user)
    await db.flush()
    partner = _partner(user.id)
    db.add(partner)
    await db.flush()
    return partner


@pytest.mark.asyncio
async def test_partner_creation_is_queued_once(db_session: AsyncSession):
    await _installation(db_session)
    partner = await _saved_partner(db_session)

    first = await schedule_partner_creation(db_session, partner)
    second = await schedule_partner_creation(db_session, partner)

    count = await db_session.scalar(select(func.count(BitrixOutboxOperation.id)))
    operation = await db_session.scalar(select(BitrixOutboxOperation))
    assert first is True
    assert second is False
    assert count == 1
    assert operation is not None
    assert operation.local_entity_type == PARTNER_ENTITY_TYPE
    assert partner.bitrix_sync_status == "pending"
    assert partner.bitrix_collab_status == "binding_required"


@pytest.mark.asyncio
async def test_pending_partner_is_not_queued(db_session: AsyncSession):
    await _installation(db_session)
    partner = await _saved_partner(db_session)
    partner.status = "pending"

    queued = await schedule_partner_creation(db_session, partner)

    count = await db_session.scalar(select(func.count(BitrixOutboxOperation.id)))
    assert queued is False
    assert count == 0
    assert partner.bitrix_sync_status == "not_scheduled"


@pytest.mark.asyncio
async def test_remote_update_marks_conflict_without_overwriting_partner(db_session: AsyncSession):
    installation = await _installation(db_session)
    partner = await _saved_partner(db_session)
    original_company = partner.company_name
    db_session.add(
        BitrixEntityMap(
            member_id=installation.member_id,
            local_entity_type=PARTNER_ENTITY_TYPE,
            local_entity_id=partner.id,
            bitrix_entity_type="crm_dynamic_1070",
            bitrix_entity_id="321",
        )
    )
    await db_session.flush()
    remote_item = _remote_item(partner)
    remote_item[PARTNER_FIELDS["company_name"]] = 'ООО "Изменено в Битрикс24"'

    changed = await mark_remote_partner_conflict(
        db_session,
        member_id=installation.member_id,
        event_name="ONCRMDYNAMICITEMUPDATE",
        payload={"data[FIELDS][ENTITY_TYPE_ID]": "1070", "data[FIELDS][ID]": "321"},
        remote_item=remote_item,
    )

    assert changed is True
    assert partner.bitrix_sync_status == "conflict"
    assert partner.bitrix_sync_error_code == "REMOTE_PROFILE_CHANGED"
    assert partner.company_name == original_company


@pytest.mark.asyncio
async def test_remote_non_profile_update_does_not_create_false_conflict(db_session: AsyncSession):
    installation = await _installation(db_session)
    partner = await _saved_partner(db_session)
    partner.bitrix_sync_status = "conflict"
    partner.bitrix_sync_error_code = "REMOTE_PROFILE_CHANGED"
    mapping = BitrixEntityMap(
        member_id=installation.member_id,
        local_entity_type=PARTNER_ENTITY_TYPE,
        local_entity_id=partner.id,
        bitrix_entity_type="crm_dynamic_1070",
        bitrix_entity_id="321",
    )
    db_session.add(mapping)
    await db_session.flush()
    remote_item = _remote_item(partner)
    remote_item["title"] = "Служебное изменение роботом"
    remote_item[PARTNER_FIELDS["phone"]] = "8 (999) 000-00-00"
    remote_item[PARTNER_FIELDS["legal_address"]] = f"{partner.legal_address}|55.75;37.62|123"
    remote_item[PARTNER_FIELDS["court_fee"]] = "RUB|15000"
    remote_item[PARTNER_FIELDS["payment_days"]] = "10"

    changed = await mark_remote_partner_conflict(
        db_session,
        member_id=installation.member_id,
        event_name="ONCRMDYNAMICITEMUPDATE",
        payload={"data[FIELDS][ENTITY_TYPE_ID]": "1070", "data[FIELDS][ID]": "321"},
        remote_item=remote_item,
    )

    assert changed is False
    assert partner.bitrix_sync_status == "synced"
    assert partner.bitrix_sync_error_code is None
    assert mapping.last_verified_at is not None


@pytest.mark.asyncio
async def test_periodic_reconciliation_repairs_existing_false_conflict(db_session: AsyncSession):
    installation = await _installation(db_session)
    partner = await _saved_partner(db_session)
    partner.bitrix_sync_status = "conflict"
    partner.bitrix_sync_error_code = "REMOTE_PROFILE_CHANGED"
    mapping = BitrixEntityMap(
        member_id=installation.member_id,
        local_entity_type=PARTNER_ENTITY_TYPE,
        local_entity_id=partner.id,
        bitrix_entity_type="crm_dynamic_1070",
        bitrix_entity_id="321",
    )
    db_session.add(mapping)
    await db_session.flush()

    remote = AsyncMock()
    remote.call.return_value = {"item": _remote_item(partner)}
    context = AsyncMock()
    context.__aenter__.return_value = remote
    with (
        patch("app.integrations.bitrix24.partners._installation_token", new=AsyncMock(return_value="token")),
        patch("app.integrations.bitrix24.partners.Bitrix24Client", return_value=context),
    ):
        result = await reconcile_remote_partner_profiles(db_session, limit=25)

    assert result == {"claimed": 1, "synced": 1, "conflicts": 0, "failed": 0}
    assert partner.bitrix_sync_status == "synced"
    assert partner.bitrix_sync_error_code is None
    assert mapping.last_verified_at is not None
    remote.call.assert_awaited_once_with(
        "crm.item.get",
        {
            "entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
            "id": "321",
            "useOriginalUfNames": "Y",
        },
    )
