from io import BytesIO
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _create_partner_and_client(client: AsyncClient, setup_db):
    from app.models.client import Client
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="file_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        partner = Partner(
            user_id=user.id,
            company_name="Test Co",
            director_name="Dir",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.flush()
        cl = Client(partner_id=partner.id, type="before_court", status="new", full_name="Test Client")
        session.add(cl)
        await session.commit()
        client_id = str(cl.id)

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "file_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token, client_id


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestFileUpload:
    @patch("app.api.files.upload_file_async", new_callable=AsyncMock)
    @patch("app.api.files.get_presigned_url_async", new_callable=AsyncMock)
    async def test_upload_success(self, mock_url, mock_upload, client: AsyncClient, setup_db):
        mock_upload.return_value = "uploads/test-uuid.pdf"
        mock_url.return_value = "https://s3.example.com/uploads/test-uuid.pdf"

        token, client_id = await _create_partner_and_client(client, setup_db)
        file_content = b"%PDF-1.4 test content"
        resp = await client.post(
            "/api/v1/upload",
            params={"client_id": client_id, "document_type": "passport"},
            files={"file": ("test.pdf", BytesIO(file_content), "application/pdf")},
            headers=auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "test.pdf"
        assert data["document_type"] == "passport"
        assert data["size"] == len(file_content)
        mock_upload.assert_called_once()

    async def test_upload_wrong_extension(self, client: AsyncClient, setup_db):
        token, client_id = await _create_partner_and_client(client, setup_db)
        resp = await client.post(
            "/api/v1/upload",
            params={"client_id": client_id},
            files={"file": ("test.exe", BytesIO(b"binary"), "application/octet-stream")},
            headers=auth(token),
        )
        assert resp.status_code == 415

    async def test_upload_wrong_mime(self, client: AsyncClient, setup_db):
        token, client_id = await _create_partner_and_client(client, setup_db)
        resp = await client.post(
            "/api/v1/upload",
            params={"client_id": client_id},
            files={"file": ("test.pdf", BytesIO(b"binary"), "text/plain")},
            headers=auth(token),
        )
        assert resp.status_code == 415

    @patch("app.api.files.upload_file_async", new_callable=AsyncMock)
    @patch("app.api.files.get_presigned_url_async", new_callable=AsyncMock)
    async def test_get_file_url(self, mock_url, mock_upload, client: AsyncClient, setup_db):
        mock_upload.return_value = "uploads/test.pdf"
        mock_url.return_value = "https://s3.example.com/uploads/test.pdf"

        token, client_id = await _create_partner_and_client(client, setup_db)
        upload_resp = await client.post(
            "/api/v1/upload",
            params={"client_id": client_id},
            files={"file": ("test.pdf", BytesIO(b"%PDF"), "application/pdf")},
            headers=auth(token),
        )
        file_id = upload_resp.json()["file_id"]

        resp = await client.get(f"/api/v1/files/{file_id}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["url"] is not None

    @patch("app.api.files.upload_file_async", new_callable=AsyncMock)
    @patch("app.api.files.get_presigned_url_async", new_callable=AsyncMock)
    @patch("app.api.files.delete_file_async", new_callable=AsyncMock)
    async def test_delete_file(self, mock_del, mock_url, mock_upload, client: AsyncClient, setup_db):
        mock_upload.return_value = "uploads/test.pdf"
        mock_url.return_value = "https://s3.example.com/uploads/test.pdf"

        token, client_id = await _create_partner_and_client(client, setup_db)
        upload_resp = await client.post(
            "/api/v1/upload",
            params={"client_id": client_id},
            files={"file": ("test.pdf", BytesIO(b"%PDF"), "application/pdf")},
            headers=auth(token),
        )
        file_id = upload_resp.json()["file_id"]

        resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth(token))
        assert resp.status_code == 204
        mock_del.assert_called_once()
