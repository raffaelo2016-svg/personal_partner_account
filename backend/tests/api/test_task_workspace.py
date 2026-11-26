from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.client import Client
from app.models.partner import Partner
from app.models.task import Task
from app.models.user import User
from tests.conftest import async_session_test


@pytest.fixture(autouse=True)
def _no_redis_blacklist():
    with patch("app.services.auth_service.is_access_jti_revoked", AsyncMock(return_value=False)):
        yield


async def _seed():
    async with async_session_test() as session:
        partner_user = User(
            email="workspace-partner@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        admin_user = User(
            email="workspace-admin@test.com",
            full_name="Админ Тестов",
            hashed_password=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        other_user = User(
            email="workspace-other@test.com",
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
        )
        session.add_all([partner_user, admin_user, other_user])
        await session.flush()
        partner = Partner(
            user_id=partner_user.id,
            company_name="Workspace Partner",
            director_name="Director",
            inn="7701234567",
            phone="+71234567890",
            status="active",
        )
        other_partner = Partner(
            user_id=other_user.id,
            company_name="Other Partner",
            director_name="Director",
            inn="7701234568",
            phone="+71234567891",
            status="active",
        )
        session.add_all([partner, other_partner])
        await session.flush()
        client = Client(
            partner_id=partner.id,
            type="before_court",
            status="new",
            full_name="Workspace Client",
        )
        session.add(client)
        await session.flush()
        task = Task(
            partner_id=partner.id,
            client_id=client.id,
            title="Workspace task",
            description="Task with documents and chat",
            status="pending",
            priority="high",
            assigned_to="uritech",
            created_by=partner_user.id,
        )
        partner_task = Task(
            partner_id=partner.id,
            client_id=client.id,
            title="Task assigned to partner",
            description="Admin asks the partner to prepare documents",
            status="in_progress",
            priority="medium",
            assigned_to="partner",
            created_by=admin_user.id,
        )
        session.add_all([task, partner_task])
        await session.commit()
        return {
            "partner_token": create_access_token({"sub": str(partner_user.id)}),
            "admin_token": create_access_token({"sub": str(admin_user.id)}),
            "other_token": create_access_token({"sub": str(other_user.id)}),
            "task_id": str(task.id),
            "partner_task_id": str(partner_task.id),
            "client_id": str(client.id),
        }


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_task_detail_and_visibility(client: AsyncClient, setup_db):
    data = await _seed()
    response = await client.get(f"/api/v1/tasks/{data['task_id']}", headers=_headers(data["partner_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Workspace task"
    assert body["client"]["full_name"] == "Workspace Client"
    assert body["permissions"]["can_request_review"] is False
    assert body["files"] == []

    partner_task_view = await client.get(
        f"/api/v1/tasks/{data['partner_task_id']}", headers=_headers(data["partner_token"])
    )
    assert partner_task_view.status_code == 200
    assert partner_task_view.json()["permissions"]["can_request_review"] is True

    admin_view = await client.get(f"/api/v1/tasks/{data['task_id']}", headers=_headers(data["admin_token"]))
    assert admin_view.status_code == 200
    assert admin_view.json()["permissions"]["is_admin"] is True

    forbidden = await client.get(f"/api/v1/tasks/{data['task_id']}", headers=_headers(data["other_token"]))
    assert forbidden.status_code == 403


async def test_review_flow_and_admin_approval(client: AsyncClient, setup_db):
    data = await _seed()
    wrong_direction = await client.post(
        f"/api/v1/tasks/{data['task_id']}/review",
        json={"action": "request"},
        headers=_headers(data["partner_token"]),
    )
    assert wrong_direction.status_code == 400

    requested = await client.post(
        f"/api/v1/tasks/{data['partner_task_id']}/review",
        json={"action": "request"},
        headers=_headers(data["partner_token"]),
    )
    assert requested.status_code == 200
    assert requested.json()["review_requested_at"] is not None
    assert requested.json()["status"] == "in_progress"

    admin_request = await client.post(
        f"/api/v1/tasks/{data['partner_task_id']}/review",
        json={"action": "request"},
        headers=_headers(data["admin_token"]),
    )
    assert admin_request.status_code == 403

    approved = await client.post(
        f"/api/v1/tasks/{data['partner_task_id']}/review",
        json={"action": "approve"},
        headers=_headers(data["admin_token"]),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"
    assert approved.json()["review_requested_at"] is None
    assert approved.json()["completed_at"] is not None


async def test_admin_executes_partner_request_without_review(client: AsyncClient, setup_db):
    data = await _seed()
    started = await client.put(
        f"/api/v1/tasks/{data['task_id']}",
        json={"status": "in_progress"},
        headers=_headers(data["admin_token"]),
    )
    assert started.status_code == 200
    assert started.json()["review_requested_at"] is None

    completed = await client.put(
        f"/api/v1/tasks/{data['task_id']}",
        json={"status": "completed"},
        headers=_headers(data["admin_token"]),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["review_requested_at"] is None

    partner_view = await client.get(f"/api/v1/tasks/{data['task_id']}", headers=_headers(data["partner_token"]))
    assert partner_view.json()["permissions"]["can_request_review"] is False


async def test_task_files_are_shared_with_client_and_permissions(client: AsyncClient, setup_db):
    data = await _seed()
    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    with (
        patch("app.services.task_service.upload_file_async", AsyncMock(return_value="uploads/task.pdf")),
        patch("app.services.task_service.download_file_async", AsyncMock(return_value=pdf)),
    ):
        uploaded = await client.post(
            f"/api/v1/tasks/{data['task_id']}/files",
            files={"file": ("document.pdf", pdf, "application/pdf")},
            headers=_headers(data["partner_token"]),
        )
        assert uploaded.status_code == 201
        file_id = uploaded.json()["id"]
        assert uploaded.json()["can_delete"] is True

        task = await client.get(f"/api/v1/tasks/{data['task_id']}", headers=_headers(data["partner_token"]))
        assert [item["id"] for item in task.json()["files"]] == [file_id]

        client_files = await client.get(
            f"/api/v1/tasks/client-files/{data['client_id']}",
            headers=_headers(data["partner_token"]),
        )
        assert client_files.status_code == 200
        assert [item["id"] for item in client_files.json()] == [file_id]

        downloaded = await client.get(
            f"/api/v1/tasks/{data['task_id']}/files/{file_id}/download",
            headers=_headers(data["partner_token"]),
        )
        assert downloaded.status_code == 200
        assert downloaded.content == pdf

        foreign_delete = await client.delete(
            f"/api/v1/tasks/{data['task_id']}/files/{file_id}",
            headers=_headers(data["other_token"]),
        )
        assert foreign_delete.status_code == 403

        admin_delete = await client.delete(
            f"/api/v1/tasks/{data['task_id']}/files/{file_id}",
            headers=_headers(data["admin_token"]),
        )
        assert admin_delete.status_code == 204


async def test_task_chat_is_scoped_to_task(client: AsyncClient, setup_db):
    data = await _seed()
    sent = await client.post(
        f"/api/v1/tasks/{data['task_id']}/messages",
        json={"text": "Нужна выписка ЕГРН"},
        headers=_headers(data["partner_token"]),
    )
    assert sent.status_code == 201
    assert sent.json()["is_mine"] is True

    partner_messages = await client.get(
        f"/api/v1/tasks/{data['task_id']}/messages",
        headers=_headers(data["partner_token"]),
    )
    assert partner_messages.status_code == 200
    assert partner_messages.json()[0]["text"] == "Нужна выписка ЕГРН"

    admin_messages = await client.get(
        f"/api/v1/tasks/{data['task_id']}/messages",
        headers=_headers(data["admin_token"]),
    )
    assert admin_messages.status_code == 200
    assert admin_messages.json()[0]["is_mine"] is False

    forbidden = await client.get(
        f"/api/v1/tasks/{data['task_id']}/messages",
        headers=_headers(data["other_token"]),
    )
    assert forbidden.status_code == 403


async def test_discussion_shows_names_instead_of_emails(client: AsyncClient, setup_db):
    data = await _seed()

    partner_message = await client.post(
        f"/api/v1/tasks/{data['task_id']}/messages",
        json={"text": "Есть вопрос по задаче"},
        headers=_headers(data["partner_token"]),
    )
    assert partner_message.status_code == 201
    assert partner_message.json()["author_name"] == "Director"

    admin_message = await client.post(
        f"/api/v1/tasks/{data['task_id']}/messages",
        json={"text": "Ответили"},
        headers=_headers(data["admin_token"]),
    )
    assert admin_message.status_code == 201
    assert admin_message.json()["author_name"] == "Админ Тестов"

    messages = await client.get(
        f"/api/v1/tasks/{data['task_id']}/messages",
        headers=_headers(data["admin_token"]),
    )
    assert messages.status_code == 200
    names = [item["author_name"] for item in messages.json()]
    assert sorted(names) == sorted(["Director", "Админ Тестов"])
    assert all("@" not in name for name in names)

    await client.put(
        f"/api/v1/tasks/{data['task_id']}",
        json={"status": "in_progress"},
        headers=_headers(data["admin_token"]),
    )
    detail = await client.get(f"/api/v1/tasks/{data['task_id']}", headers=_headers(data["admin_token"]))
    actor_names = [event["actor_name"] for event in detail.json()["events"] if event["actor_name"]]
    assert "Админ Тестов" in actor_names
    assert all("@" not in name for name in actor_names)

    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    with patch("app.services.task_service.upload_file_async", AsyncMock(return_value="uploads/task.pdf")):
        uploaded = await client.post(
            f"/api/v1/tasks/{data['task_id']}/files",
            files={"file": ("document.pdf", pdf, "application/pdf")},
            headers=_headers(data["partner_token"]),
        )
    assert uploaded.status_code == 201
    assert uploaded.json()["uploader_name"] == "Director"
