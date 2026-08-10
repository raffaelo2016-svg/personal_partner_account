from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.security import hash_password


async def _setup_partner_with_client(client: AsyncClient, setup_db):
    from app.models.client import Client
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="task_partner@test.com",
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
        cl = Client(partner_id=partner.id, type="before_court", status="new", full_name="Task Test Client")
        session.add(cl)
        await session.commit()
        client_id = str(cl.id)

    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "task_partner@test.com", "password": "password123"},
        )
        token = resp.json()["access_token"]

    return token, client_id


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestTasks:
    async def test_create_task(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "client_id": client_id,
                "title": "Собрать документы",
                "due_date": str(date.today() + timedelta(days=7)),
                "assigned_to": "partner",
            },
            headers=auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Собрать документы"
        assert resp.json()["status"] == "pending"

    async def test_create_task_with_active_bitrix_projection(self, client: AsyncClient, setup_db):
        """Creating a task must return 201 when Bitrix scheduling updates it."""
        from app.config import settings
        from app.models.bitrix_installation import BitrixInstallation
        from app.models.client import Client
        from app.models.settings import SystemSetting
        from tests.conftest import async_session_test

        token, client_id = await _setup_partner_with_client(client, setup_db)
        async with async_session_test() as session:
            synced_client = await session.get(Client, client_id)
            assert synced_client is not None
            synced_client.bitrix_deal_id = "35023"
            synced_client.bitrix_sync_status = "synced"
            session.add_all(
                [
                    BitrixInstallation(
                        member_id="member-task-create",
                        portal_domain=settings.BITRIX_ALLOWED_DOMAIN,
                        client_endpoint=f"https://{settings.BITRIX_ALLOWED_DOMAIN}/rest/",
                        server_endpoint="https://oauth.bitrix.info/rest/",
                        access_token_encrypted=b"encrypted-access",
                        refresh_token_encrypted=b"encrypted-refresh",
                        status="L",
                    ),
                    SystemSetting(key="bitrix_task_responsible_uritech", value="1"),
                ]
            )
            await session.commit()

        resp = await client.post(
            "/api/v1/tasks",
            json={
                "client_id": client_id,
                "title": "Подготовить согласие",
                "description": "Подготовить документы",
                "due_date": str(date.today() + timedelta(days=1)),
                "assigned_to": "uritech",
                "priority": "high",
            },
            headers=auth(token),
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Подготовить согласие"
        assert data["bitrix_sync_status"] == "pending"
        assert data["updated_at"]

    async def test_list_tasks(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        await client.post(
            "/api/v1/tasks",
            json={"client_id": client_id, "title": "Task 1", "due_date": str(date.today()), "assigned_to": "partner"},
            headers=auth(token),
        )
        resp = await client.get("/api/v1/tasks", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_update_task(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        create_resp = await client.post(
            "/api/v1/tasks",
            json={"client_id": client_id, "title": "Task", "due_date": str(date.today()), "assigned_to": "partner"},
            headers=auth(token),
        )
        task_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/tasks/{task_id}",
            json={"status": "completed"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_at"] is not None

    async def test_task_stats(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        await client.post(
            "/api/v1/tasks",
            json={"client_id": client_id, "title": "Task", "due_date": str(date.today()), "assigned_to": "partner"},
            headers=auth(token),
        )
        resp = await client.get("/api/v1/tasks/stats", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_urgent_tasks(self, client: AsyncClient, setup_db):
        token, client_id = await _setup_partner_with_client(client, setup_db)
        await client.post(
            "/api/v1/tasks",
            json={
                "client_id": client_id,
                "title": "Urgent!",
                "due_date": str(date.today()),
                "assigned_to": "partner",
                "priority": "high",
            },
            headers=auth(token),
        )
        resp = await client.get("/api/v1/tasks/urgent", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
