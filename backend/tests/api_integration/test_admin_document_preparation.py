from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select

from app.models.file_upload import FileUpload
from app.models.notification import Notification
from tests.api_integration.conftest import auth, create_client
from tests.conftest import async_session_test


async def test_admin_generates_and_stores_uritech_documents(
    client: AsyncClient,
    partner_token,
    partner_user,
    admin_token,
):
    created = await create_client(client, partner_token, full_name="Петров Пётр Петрович")
    client_id = created["id"]

    with patch(
        "app.api.admin_clients.upload_file_async",
        new_callable=AsyncMock,
        side_effect=lambda _content, filename, _mime: f"uploads/{filename}.docx",
    ):
        for kind in ("application", "creditors", "inventory"):
            response = await client.post(
                f"/api/v1/admin/clients/{client_id}/documents/{kind}",
                headers=auth(admin_token),
            )
            assert response.status_code == 200
            assert response.content.startswith(b"PK")

    async with async_session_test() as session:
        document_types = set(
            await session.scalars(select(FileUpload.document_type).where(FileUpload.client_id == client_id))
        )
        assert document_types == {"generated_application", "generated_creditors", "generated_inventory"}
        notification = await session.scalar(
            select(Notification).where(
                Notification.user_id == partner_user.id,
                Notification.type == "court_documents_ready",
            )
        )
        assert notification is not None
        assert notification.link == f"/dashboard/clients/{client_id}#client-files"


async def test_admin_generation_rejects_partner_preparation_mode(
    client: AsyncClient,
    partner_token,
    admin_token,
):
    created = await create_client(client, partner_token)
    await client.put(
        f"/api/v1/clients/{created['id']}",
        json={"document_preparation_mode": "partner"},
        headers=auth(partner_token),
    )

    response = await client.post(
        f"/api/v1/admin/clients/{created['id']}/documents/application",
        headers=auth(admin_token),
    )
    assert response.status_code == 400


async def test_partner_cannot_use_admin_generation_endpoint(
    client: AsyncClient,
    partner_token,
):
    created = await create_client(client, partner_token)
    response = await client.post(
        f"/api/v1/admin/clients/{created['id']}/documents/application",
        headers=auth(partner_token),
    )
    assert response.status_code == 403
