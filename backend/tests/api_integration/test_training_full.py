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


class TestTrainingProgress:
    async def test_progress_starts_empty(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/training/progress", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json() == {"completed": []}

    async def test_complete_lesson(self, client: AsyncClient, partner_token):
        resp = await client.put("/api/v1/training/progress/intro", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["completed"] == ["intro"]

        again = await client.get("/api/v1/training/progress", headers=auth(partner_token))
        assert again.json()["completed"] == ["intro"]

    async def test_completing_twice_is_idempotent(self, client: AsyncClient, partner_token):
        first = await client.put("/api/v1/training/progress/intro", headers=auth(partner_token))
        second = await client.put("/api/v1/training/progress/intro", headers=auth(partner_token))
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["completed"] == ["intro"]

    async def test_progress_lists_every_completed_lesson(self, client: AsyncClient, partner_token):
        await client.put("/api/v1/training/progress/client", headers=auth(partner_token))
        await client.put("/api/v1/training/progress/intro", headers=auth(partner_token))
        resp = await client.get("/api/v1/training/progress", headers=auth(partner_token))
        assert sorted(resp.json()["completed"]) == ["client", "intro"]

    async def test_reset_lesson(self, client: AsyncClient, partner_token):
        await client.put("/api/v1/training/progress/intro", headers=auth(partner_token))
        resp = await client.delete("/api/v1/training/progress/intro", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["completed"] == []

    async def test_reset_missing_lesson_is_ok(self, client: AsyncClient, partner_token):
        resp = await client.delete("/api/v1/training/progress/finance", headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["completed"] == []

    async def test_rejects_unknown_key_format(self, client: AsyncClient, partner_token):
        resp = await client.put("/api/v1/training/progress/1bad-key", headers=auth(partner_token))
        assert resp.status_code == 422

    async def test_progress_is_per_partner(self, client: AsyncClient, partner_token, partner_token2):
        await client.put("/api/v1/training/progress/intro", headers=auth(partner_token))
        other = await client.get("/api/v1/training/progress", headers=auth(partner_token2))
        assert other.json()["completed"] == []

    async def test_progress_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/training/progress")
        assert resp.status_code in (401, 403)
