"""Files: deletion from the cabinet."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models.file_deletion_tombstone import FileDeletionTombstone
from app.models.file_upload import FileUpload
from tests.api_integration.conftest import auth, create_client
from tests.conftest import async_session_test


async def _create_file(
    client_id: str,
    *,
    bitrix_disk_file_id: str | None = None,
    bitrix_sync_status: str = "synced",
) -> str:
    async with async_session_test() as session:
        record = FileUpload(
            client_id=uuid.UUID(client_id),
            document_type="passport",
            original_name="паспорт.pdf",
            s3_key=f"uploads/{uuid.uuid4()}.pdf",
            size=12,
            mime_type="application/pdf",
            content_sha256=uuid.uuid4().hex,
            bitrix_sync_status=bitrix_sync_status,
            bitrix_disk_file_id=bitrix_disk_file_id,
        )
        session.add(record)
        await session.commit()
        return str(record.id)


class TestFileDeletion:
    async def test_partner_deletes_own_document(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        file_id = await _create_file(c["id"])

        resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth(partner_token))
        assert resp.status_code == 204

        listed = await client.get("/api/v1/files", params={"client_id": c["id"]}, headers=auth(partner_token))
        assert listed.status_code == 200
        assert listed.json() == []

        async with async_session_test() as session:
            assert await session.get(FileUpload, uuid.UUID(file_id)) is None

    async def test_deleting_synced_document_leaves_tombstone(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        file_id = await _create_file(c["id"], bitrix_disk_file_id="9001")

        resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth(partner_token))
        assert resp.status_code == 204

        async with async_session_test() as session:
            tombstone = await session.scalar(
                select(FileDeletionTombstone).where(
                    FileDeletionTombstone.client_id == uuid.UUID(c["id"]),
                    FileDeletionTombstone.bitrix_disk_file_id == "9001",
                )
            )
        assert tombstone is not None
        # The tombstone keeps only the remote ID: no name, size or content.
        assert not hasattr(tombstone, "original_name")

    async def test_file_that_was_never_synced_leaves_no_tombstone(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        file_id = await _create_file(c["id"], bitrix_sync_status="not_scheduled")

        resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth(partner_token))
        assert resp.status_code == 204

        async with async_session_test() as session:
            tombstones = list(
                (
                    await session.scalars(
                        select(FileDeletionTombstone).where(FileDeletionTombstone.client_id == uuid.UUID(c["id"]))
                    )
                ).all()
            )
        assert tombstones == []

    async def test_other_partner_cannot_delete_document(self, client: AsyncClient, partner_token, partner_token2):
        c = await create_client(client, partner_token)
        file_id = await _create_file(c["id"])

        resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth(partner_token2))
        assert resp.status_code == 403

        async with async_session_test() as session:
            assert await session.get(FileUpload, uuid.UUID(file_id)) is not None

    async def test_deleting_unknown_document_returns_404(self, client: AsyncClient, partner_token):
        resp = await client.delete(
            "/api/v1/files/00000000-0000-0000-0000-000000000000",
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_deleting_document_while_sync_is_running_returns_409(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        file_id = await _create_file(c["id"], bitrix_sync_status="processing")

        resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth(partner_token))
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "BITRIX_SYNC_IN_PROGRESS"

        async with async_session_test() as session:
            assert await session.get(FileUpload, uuid.UUID(file_id)) is not None
