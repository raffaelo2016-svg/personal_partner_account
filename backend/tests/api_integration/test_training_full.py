"""Полные API-тесты: Обучение — videos, faq, instructions, important."""

from httpx import AsyncClient

from tests.api_integration.conftest import auth


class TestTraining:
    async def test_videos(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/training/videos", headers=auth(partner_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_faq(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/training/faq", headers=auth(partner_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_instructions(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/training/instructions", headers=auth(partner_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_important(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/training/important", headers=auth(partner_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_idempotent(self, client: AsyncClient, partner_token):
        r1 = (await client.get("/api/v1/training/faq", headers=auth(partner_token))).json()
        r2 = (await client.get("/api/v1/training/faq", headers=auth(partner_token))).json()
        assert r1 == r2

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/training/videos")
        assert resp.status_code in (401, 403)
