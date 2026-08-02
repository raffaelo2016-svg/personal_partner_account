from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient

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
