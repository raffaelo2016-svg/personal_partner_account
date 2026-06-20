from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_partner(client: AsyncClient, setup_db):
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="training_partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        partner = Partner(
            user_id=user.id,
            company_name="Training Co",
            director_name="Dir",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        session.add(partner)
        await session.commit()

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "training_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_training(setup_db):
    from app.models.training import FAQ, ImportantNote, Instruction, TrainingVideo
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        session.add(
            TrainingVideo(
                title="Intro",
                video_url="https://example.com/video.mp4",
                description="Introduction video",
                duration=120,
                order=1,
            )
        )
        session.add(
            FAQ(
                question="How to add a client?",
                answer="Use the client form.",
                order=1,
            )
        )
        session.add(
            Instruction(
                title="Getting started",
                steps={"items": ["Step 1", "Step 2"]},
                order=1,
            )
        )
        session.add(
            ImportantNote(
                title="Pay on time",
                description="Important payment info",
                icon="alert",
                order=1,
            )
        )
        await session.commit()


@pytest.mark.asyncio
class TestTraining:
    async def test_list_videos(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        await _seed_training(setup_db)
        resp = await client.get("/api/v1/training/videos", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["title"] == "Intro"

    async def test_list_faq(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        await _seed_training(setup_db)
        resp = await client.get("/api/v1/training/faq", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["question"] == "How to add a client?"

    async def test_list_instructions(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        await _seed_training(setup_db)
        resp = await client.get(
            "/api/v1/training/instructions",
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["title"] == "Getting started"

    async def test_list_important(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        await _seed_training(setup_db)
        resp = await client.get(
            "/api/v1/training/important",
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["title"] == "Pay on time"

    async def test_empty_lists(self, client: AsyncClient, setup_db):
        token = await _setup_partner(client, setup_db)
        for endpoint in ["videos", "faq", "instructions", "important"]:
            resp = await client.get(
                f"/api/v1/training/{endpoint}",
                headers=auth(token),
            )
            assert resp.status_code == 200
            assert resp.json() == []
