import uuid
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixInboundEvent
from app.models.client import Client
from tests.api_integration.conftest import auth, create_client
from tests.conftest import async_session_test


@pytest.fixture(autouse=True)
def disable_token_revocation_lookup():
    with patch("app.services.auth_service.is_access_jti_revoked", new=AsyncMock(return_value=False)):
        yield


class TestAdminBitrixAttention:
    async def test_lists_attention_without_personal_data(self, client: AsyncClient, admin_token, partner_token):
        created = await create_client(client, partner_token, full_name="Скрытое Имя")
        async with async_session_test() as session:
            record = await session.get(Client, UUID(created["id"]))
            record.bitrix_sync_status = "failed"
            record.bitrix_sync_error_code = "TRANSPORT_ERROR"
            await session.commit()

        response = await client.get(
            "/api/v1/admin/bitrix-attention",
            params={"entity_type": "client"},
            headers=auth(admin_token),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["entity_id"] == created["id"]
        assert body["items"][0]["error_code"] == "TRANSPORT_ERROR"
        assert "Скрытое Имя" not in response.text
        assert "phone" not in response.text

    async def test_partner_cannot_read_attention(self, client: AsyncClient, partner_token):
        response = await client.get("/api/v1/admin/bitrix-attention", headers=auth(partner_token))
        assert response.status_code == 403

    async def test_lists_incomplete_inbound_client_and_allows_retry(self, client: AsyncClient, admin_token):
        receipt_id = uuid.uuid4()
        async with async_session_test() as session:
            session.add(
                BitrixInstallation(
                    member_id="attention-test-member",
                    portal_domain="bitrix.example.ru",
                    client_endpoint="https://bitrix.example.ru/rest/",
                    server_endpoint="https://oauth.bitrix.info/rest/",
                    access_token_encrypted=b"token",
                    refresh_token_encrypted=b"refresh",
                )
            )
            session.add(
                BitrixInboundEvent(
                    id=receipt_id,
                    member_id="attention-test-member",
                    event_key="attention-inbound-client",
                    event_name="ONCRMDEALADD",
                    remote_entity_type="client_deal",
                    remote_entity_id="321",
                    payload_hash="a" * 64,
                    status="failed",
                    attempts=8,
                    error_code="CLIENT_TYPE_REQUIRED",
                )
            )
            await session.commit()

        response = await client.get(
            "/api/v1/admin/bitrix-attention",
            params={"entity_type": "inbound_client"},
            headers=auth(admin_token),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["counts"]["inbound_client"] == 1
        assert body["items"][0] == {
            "entity_type": "inbound_client",
            "entity_id": str(receipt_id),
            "parent_id": None,
            "sync_status": "conflict",
            "error_code": "CLIENT_TYPE_REQUIRED",
            "occurred_at": body["items"][0]["occurred_at"],
            "remote_id": "321",
            "external_url": "https://bitrix.example.ru/crm/deal/details/321/",
        }

        retry = await client.post(
            f"/api/v1/admin/bitrix-attention/inbound-clients/{receipt_id}/retry",
            headers=auth(admin_token),
        )
        assert retry.status_code == 204

        async with async_session_test() as session:
            receipt = await session.get(BitrixInboundEvent, receipt_id)
            assert receipt is not None
            assert receipt.status == "received"
            assert receipt.attempts == 0
            assert receipt.error_code is None
