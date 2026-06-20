"""Files: list, edge cases."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth, create_client


class TestFilesEdgeCases:
    async def test_list_files_empty(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.get(
            "/api/v1/files",
            params={"client_id": c["id"]},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_nonexistent_file(self, client: AsyncClient, partner_token):
        resp = await client.get(
            "/api/v1/files/00000000-0000-0000-0000-000000000000",
            headers=auth(partner_token),
        )
        assert resp.status_code == 404

    async def test_upload_wrong_extension(self, client: AsyncClient, partner_token):
        c = await create_client(client, partner_token)
        resp = await client.post(
            "/api/v1/upload",
            params={"client_id": c["id"]},
            files={"file": ("virus.exe", b"data", "application/octet-stream")},
            headers=auth(partner_token),
        )
        assert resp.status_code in (400, 415, 422)
