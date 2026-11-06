"""Tests for routing chat attachments into client documents."""

import hashlib
import uuid
from io import BytesIO
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select

from tests.chat.conftest import auth
from tests.conftest import async_session_test

PDF_CONTENT = b"%PDF-1.4 chat document"


async def _create_client(partner, full_name: str = "Иванов Иван Иванович", status: str = "documents_collection"):
    from app.models.client import Client

    async with async_session_test() as session:
        client = Client(
            partner_id=partner.id,
            type="before_court",
            status=status,
            full_name=full_name,
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)
        return client


async def _send_partner_attachment(
    http: AsyncClient,
    token: str,
    *,
    text: str = "Иван Иванович, паспорт",
    filename: str = "Паспорт_Иванов.pdf",
    content: bytes = PDF_CONTENT,
) -> tuple[str, str]:
    rooms = (await http.get("/api/v1/chat/rooms", headers=auth(token))).json()
    room = next(room for room in rooms if room["type"] == "admin")
    with patch("app.services.chat_service.upload_file_async", new_callable=AsyncMock) as upload:
        upload.return_value = "uploads/chat/attachment.pdf"
        response = await http.post(
            f"/api/v1/chat/rooms/{room['id']}/attachments",
            data={"text": text},
            files={"file": (filename, BytesIO(content), "application/pdf")},
            headers=auth(token),
        )
    assert response.status_code == 201, response.text
    return response.json()["id"], room["id"]


def _patch_storage():
    return (
        patch("app.services.chat_documents.download_file_async", new_callable=AsyncMock),
        patch("app.services.chat_documents.upload_file_async", new_callable=AsyncMock),
    )


class TestDocumentInboxList:
    async def test_lists_partner_attachment_with_candidates(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response = await client.get("/api/v1/admin/chat/document-inbox", headers=auth(admin_token))
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["message_id"] == message_id
        assert item["status"] == "unassigned"
        assert item["sender_label"] == "Партнёр"
        assert item["attachment"]["filename"] == "Паспорт_Иванов.pdf"
        assert item["candidates"][0]["full_name"] == "Иванов Иван Иванович"
        assert item["candidates"][0]["matched_on"] == "filename"

    async def test_count_matches_inbox(self, client: AsyncClient, admin_token, partner_token):
        await _send_partner_attachment(client, partner_token)
        response = await client.get("/api/v1/admin/chat/document-inbox/count", headers=auth(admin_token))
        assert response.status_code == 200
        assert response.json() == {"unassigned": 1}

    async def test_partner_cannot_open_inbox(self, client: AsyncClient, partner_token):
        response = await client.get("/api/v1/admin/chat/document-inbox", headers=auth(partner_token))
        assert response.status_code == 403

    async def test_item_by_message_id(self, client: AsyncClient, admin_token, partner_token):
        message_id, _ = await _send_partner_attachment(client, partner_token)
        response = await client.get(
            f"/api/v1/admin/chat/document-inbox/items/{message_id}",
            headers=auth(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["message_id"] == message_id


class TestAssignDocument:
    async def test_assign_creates_document_and_chat_note(
        self,
        client: AsyncClient,
        admin_token,
        partner_user,
        partner_token,
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, room_id = await _send_partner_attachment(client, partner_token)

        download_patch, upload_patch = _patch_storage()
        with download_patch as download, upload_patch as upload:
            download.return_value = PDF_CONTENT
            upload.return_value = "uploads/copy/passport.pdf"
            response = await client.post(
                f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
                json={"client_id": str(document_client.id), "document_type": "passport"},
                headers=auth(admin_token),
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "assigned"
        assert payload["client_id"] == str(document_client.id)
        assert payload["document_type"] == "passport"
        assert payload["file_id"]

        from app.models.chat import ChatMessage
        from app.models.file_upload import FileUpload

        async with async_session_test() as session:
            file_record = await session.get(FileUpload, payload["file_id"])
            assert file_record is not None
            assert file_record.client_id == document_client.id
            assert file_record.document_type == "passport"
            assert file_record.s3_key == "uploads/copy/passport.pdf"
            assert file_record.content_sha256 == hashlib.sha256(PDF_CONTENT).hexdigest()
            assert file_record.size == len(PDF_CONTENT)

            note = await session.scalar(
                select(ChatMessage).where(
                    ChatMessage.room_id == uuid.UUID(room_id),
                    ChatMessage.sender_type == "system",
                )
            )
            assert note is not None
            assert "прикреплён" in note.text

        count = await client.get("/api/v1/admin/chat/document-inbox/count", headers=auth(admin_token))
        assert count.json()["unassigned"] == 0

    async def test_second_assign_conflicts(
        self,
        client: AsyncClient,
        admin_token,
        partner_user,
        partner_token,
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        download_patch, upload_patch = _patch_storage()
        with download_patch as download, upload_patch as upload:
            download.return_value = PDF_CONTENT
            upload.return_value = "uploads/copy/passport.pdf"
            first = await client.post(
                f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
                json={"client_id": str(document_client.id), "document_type": "passport"},
                headers=auth(admin_token),
            )
            assert first.status_code == 200
            second = await client.post(
                f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
                json={"client_id": str(document_client.id), "document_type": "snils"},
                headers=auth(admin_token),
            )
        assert second.status_code == 409

    async def test_foreign_client_is_forbidden(
        self,
        client: AsyncClient,
        admin_token,
        partner_user2,
        partner_token,
    ):
        _, other_partner = partner_user2
        foreign_client = await _create_client(other_partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response = await client.post(
            f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
            json={"client_id": str(foreign_client.id), "document_type": "passport"},
            headers=auth(admin_token),
        )
        assert response.status_code == 403

    async def test_unknown_document_type_rejected(
        self,
        client: AsyncClient,
        admin_token,
        partner_user,
        partner_token,
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response = await client.post(
            f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
            json={"client_id": str(document_client.id), "document_type": "hacked"},
            headers=auth(admin_token),
        )
        assert response.status_code == 400

    async def test_same_content_reuses_existing_document(
        self,
        client: AsyncClient,
        admin_token,
        partner_user,
        partner_token,
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        from app.models.file_upload import FileUpload

        async with async_session_test() as session:
            existing = FileUpload(
                client_id=document_client.id,
                document_type="passport",
                original_name="already-uploaded.pdf",
                s3_key="uploads/existing/passport.pdf",
                size=len(PDF_CONTENT),
                mime_type="application/pdf",
                content_sha256=hashlib.sha256(PDF_CONTENT).hexdigest(),
            )
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            existing_id = existing.id

        download_patch, upload_patch = _patch_storage()
        with download_patch as download, upload_patch as upload:
            download.return_value = PDF_CONTENT
            response = await client.post(
                f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
                json={"client_id": str(document_client.id), "document_type": "passport"},
                headers=auth(admin_token),
            )
            assert response.status_code == 200, response.text
            upload.assert_not_called()

        assert response.json()["file_id"] == str(existing_id)


class TestIgnoreAttachment:
    async def test_ignore_removes_from_unassigned(
        self,
        client: AsyncClient,
        admin_token,
        partner_user,
        partner_token,
    ):
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response = await client.post(
            f"/api/v1/admin/chat/document-inbox/items/{message_id}/ignore",
            headers=auth(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

        unassigned = await client.get("/api/v1/admin/chat/document-inbox", headers=auth(admin_token))
        assert unassigned.json()["total"] == 0

        ignored = await client.get(
            "/api/v1/admin/chat/document-inbox",
            params={"status": "ignored"},
            headers=auth(admin_token),
        )
        assert ignored.json()["total"] == 1

    async def test_ignore_after_assign_conflicts(
        self,
        client: AsyncClient,
        admin_token,
        partner_user,
        partner_token,
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        download_patch, upload_patch = _patch_storage()
        with download_patch as download, upload_patch as upload:
            download.return_value = PDF_CONTENT
            upload.return_value = "uploads/copy/passport.pdf"
            assigned = await client.post(
                f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
                json={"client_id": str(document_client.id), "document_type": "passport"},
                headers=auth(admin_token),
            )
            assert assigned.status_code == 200

        response = await client.post(
            f"/api/v1/admin/chat/document-inbox/items/{message_id}/ignore",
            headers=auth(admin_token),
        )
        assert response.status_code == 409


class TestAssignDocumentRename:
    async def _assign(self, client, admin_token, message_id, client_id, **extra):
        download_patch, upload_patch = _patch_storage()
        with download_patch as download, upload_patch as upload:
            download.return_value = PDF_CONTENT
            upload.return_value = "uploads/copy/renamed.pdf"
            response = await client.post(
                f"/api/v1/admin/chat/document-inbox/items/{message_id}/assign",
                json={"client_id": str(client_id), "document_type": "passport", **extra},
                headers=auth(admin_token),
            )
            return response, upload

    async def test_rename_applied_to_document_and_note(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, room_id = await _send_partner_attachment(client, partner_token)

        response, _ = await self._assign(
            client,
            admin_token,
            message_id,
            document_client.id,
            filename="Паспорт_Иванов И.И..pdf",
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["document_name"] == "Паспорт_Иванов И.И.pdf"
        assert payload["duplicate"] is False

        from app.models.chat import ChatMessage
        from app.models.file_upload import FileUpload

        async with async_session_test() as session:
            file_record = await session.get(FileUpload, payload["file_id"])
            assert file_record is not None
            assert file_record.original_name == "Паспорт_Иванов И.И.pdf"
            note = await session.scalar(
                select(ChatMessage).where(
                    ChatMessage.sender_type == "system",
                    ChatMessage.room_id == uuid.UUID(room_id),
                )
            )
            assert note is not None
            assert "прикреплён как" in note.text

    async def test_extension_change_rejected(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response, upload = await self._assign(
            client,
            admin_token,
            message_id,
            document_client.id,
            filename="Паспорт.docx",
        )
        assert response.status_code == 400
        upload.assert_not_called()

    async def test_forbidden_characters_are_stripped(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response, _ = await self._assign(
            client,
            admin_token,
            message_id,
            document_client.id,
            filename="Паспорт: Иванов? .pdf",
        )
        assert response.status_code == 200, response.text
        assert response.json()["document_name"] == "Паспорт Иванов.pdf"

    async def test_long_name_is_truncated_but_keeps_extension(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response, _ = await self._assign(
            client,
            admin_token,
            message_id,
            document_client.id,
            filename=("Д" * 200) + ".pdf",
        )
        assert response.status_code == 200, response.text
        name = response.json()["document_name"]
        assert len(name) == 120
        assert name.endswith(".pdf")

    async def test_name_without_letters_rejected(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        response, upload = await self._assign(
            client,
            admin_token,
            message_id,
            document_client.id,
            filename="???",
        )
        assert response.status_code == 400
        upload.assert_not_called()

    async def test_duplicate_keeps_existing_name(
        self, client: AsyncClient, admin_token, partner_user, partner_token
    ):
        _, partner = partner_user
        document_client = await _create_client(partner)
        message_id, _ = await _send_partner_attachment(client, partner_token)

        from app.models.file_upload import FileUpload

        async with async_session_test() as session:
            existing = FileUpload(
                client_id=document_client.id,
                document_type="passport",
                original_name="Старое имя.pdf",
                s3_key="uploads/existing/old-name.pdf",
                size=len(PDF_CONTENT),
                mime_type="application/pdf",
                content_sha256=hashlib.sha256(PDF_CONTENT).hexdigest(),
            )
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            existing_id = existing.id

        response, upload = await self._assign(
            client,
            admin_token,
            message_id,
            document_client.id,
            filename="Новое имя.pdf",
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["duplicate"] is True
        assert payload["document_name"] == "Старое имя.pdf"
        assert payload["file_id"] == str(existing_id)
        upload.assert_not_called()

        async with async_session_test() as session:
            file_record = await session.get(FileUpload, existing_id)
            assert file_record.original_name == "Старое имя.pdf"
