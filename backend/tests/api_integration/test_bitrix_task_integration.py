"""Интеграция «Битрикс24 -> ЛКП»: приём задач, история статусов и действия партнёра.

Проверяем контракт из ТЗ: коды ответов, идемпотентность, разрешение конфликтов,
изоляцию партнёров и обратный поток статусов для шлюза.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.security import create_access_token, hash_password

TOKEN = "integration-test-token-0123456789abcdef"
INN_A = "3100000001"
INN_B = "3100000002"
BITRIX_URL = "https://bitrix.uriteh.ru/company/personal/user/44/tasks/task/view/18591/"


@pytest.fixture(autouse=True)
def _integration_enabled(monkeypatch):
    monkeypatch.setattr(settings, "BITRIX_INTEGRATION_TOKEN", TOKEN)


@pytest.fixture(autouse=True)
def _no_redis():
    # Проверка отзыва токена ходит в Redis; в тестах он не нужен.
    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock):
        yield


def _headers(bitrix_task_id: int = 18591, updated_at: str = "2026-11-27T10:00:00+03:00") -> dict:
    return {
        "X-Integration-Token": TOKEN,
        "Idempotency-Key": f"bitrix-{bitrix_task_id}-{updated_at}",
    }


def payload(**overrides) -> dict:
    base = {
        "bitrix_task_id": 18591,
        "bitrix_url": BITRIX_URL,
        "title": "Выдать разрешение на получение ПМ",
        "description": "Должник Савин, оформлена самозанятость",
        "deadline": "2026-12-30T23:59:00+03:00",
        "priority": "high",
        "status": "new",
        "partner": {"inn": INN_A},
        "client": {"name": "Савин Валерий Алексеевич", "deal_id": 12345},
        "author": {"name": "Евгений Самсонюк", "user_id": 57},
        "created_at": "2026-11-20T10:00:00+03:00",
        "updated_at": "2026-11-27T10:00:00+03:00",
    }
    base.update(overrides)
    return base


async def _make_partner(
    email: str,
    inn: str,
    company: str,
    *,
    bitrix_item_id: str | None = None,
) -> tuple[str, str]:
    from app.models.partner import Partner
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email=email,
            hashed_password=hash_password("password123"),
            role="partner",
            is_active=True,
            full_name="Ангелина Савина",
        )
        session.add(user)
        await session.flush()
        partner = Partner(
            user_id=user.id,
            company_name=company,
            director_name="Ангелина Савина",
            inn=inn,
            phone="+79000000000",
            status="active",
            bitrix_partner_item_id=bitrix_item_id,
        )
        session.add(partner)
        await session.commit()
        await session.refresh(user)
        await session.refresh(partner)
        return str(user.id), str(partner.id)


async def _make_admin() -> str:
    from app.models.user import User
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        user = User(
            email="manager@test.com",
            hashed_password=hash_password("manager123"),
            role="admin",
            is_active=True,
            full_name="Менеджер ЮРИТЕХ",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return str(user.id)


def auth(user_id: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


async def _tasks_count() -> int:
    from sqlalchemy import func, select

    from app.models.task import Task
    from tests.conftest import async_session_test

    async with async_session_test() as session:
        return int((await session.execute(select(func.count()).select_from(Task))).scalar() or 0)


class TestReceiveTask:
    async def test_creates_task_for_partner_by_inn(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А")

        resp = await client.post("/api/integration/tasks", json=payload(), headers=_headers())

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["lkp_task_id"]
        assert body["status"] == "new"
        assert await _tasks_count() == 1

    async def test_repeat_delivery_updates_instead_of_creating(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А")
        first = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        assert first.status_code == 201

        second = await client.post(
            "/api/integration/tasks",
            json=payload(
                title="Выдать разрешение на получение ПМ (уточнено)",
                status="in_progress",
                updated_at="2026-11-27T11:00:00+03:00",
            ),
            headers=_headers(updated_at="2026-11-27T11:00:00+03:00"),
        )

        assert second.status_code == 200, second.text
        assert second.json()["lkp_task_id"] == first.json()["lkp_task_id"]
        assert await _tasks_count() == 1

    async def test_identical_replay_is_idempotent(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А")
        first = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        replay = await client.post("/api/integration/tasks", json=payload(), headers=_headers())

        assert first.status_code == 201
        assert replay.status_code == 200
        assert replay.json()["lkp_task_id"] == first.json()["lkp_task_id"]
        assert await _tasks_count() == 1

    async def test_older_change_is_rejected_as_stale(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А")
        await client.post(
            "/api/integration/tasks",
            json=payload(updated_at="2026-11-27T12:00:00+03:00"),
            headers=_headers(updated_at="2026-11-27T12:00:00+03:00"),
        )

        stale = await client.post(
            "/api/integration/tasks",
            json=payload(title="Старая версия", updated_at="2026-11-27T09:00:00+03:00"),
            headers=_headers(updated_at="2026-11-27T09:00:00+03:00"),
        )

        assert stale.status_code == 409
        assert stale.json()["error"] == "stale_update"

    async def test_resolves_partner_by_bitrix_card(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А", bitrix_item_id="777")
        await _make_partner("b@test.com", INN_B, "Партнёр Б", bitrix_item_id="888")

        resp = await client.post(
            "/api/integration/tasks",
            json=payload(partner={"bitrix_id": 777}),
            headers=_headers(),
        )

        assert resp.status_code == 201, resp.text
        task_id = resp.json()["lkp_task_id"]
        own = await client.get(f"/api/v1/tasks/{task_id}", headers=auth(user_a))
        foreign = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=auth((await _make_partner("c@test.com", "3100000003", "Партнёр В"))[0]),
        )
        assert own.status_code == 200
        assert foreign.status_code == 404

    async def test_unknown_bitrix_card_returns_404(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А", bitrix_item_id="777")

        resp = await client.post(
            "/api/integration/tasks",
            json=payload(partner={"bitrix_id": 999}),
            headers=_headers(),
        )

        assert resp.status_code == 404
        assert resp.json()["error"] == "partner_not_found"

    async def test_card_and_inn_mismatch_returns_409(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А", bitrix_item_id="777")

        resp = await client.post(
            "/api/integration/tasks",
            json=payload(partner={"bitrix_id": 777, "inn": INN_B}),
            headers=_headers(),
        )

        assert resp.status_code == 409
        assert resp.json()["error"] == "partner_mismatch"

    async def test_card_and_inn_match_is_accepted(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А", bitrix_item_id="777")

        resp = await client.post(
            "/api/integration/tasks",
            json=payload(partner={"bitrix_id": 777, "inn": INN_A}),
            headers=_headers(),
        )

        assert resp.status_code == 201

    async def test_unknown_partner_returns_404(self, client: AsyncClient, setup_db):
        resp = await client.post("/api/integration/tasks", json=payload(), headers=_headers())

        assert resp.status_code == 404
        assert resp.json()["error"] == "partner_not_found"
        assert await _tasks_count() == 0

    async def test_same_inn_twice_returns_422(self, client: AsyncClient, setup_db):
        await _make_partner("a1@test.com", INN_A, "Партнёр А")
        await _make_partner("a2@test.com", INN_A, "Партнёр А (дубль)")

        resp = await client.post("/api/integration/tasks", json=payload(), headers=_headers())

        assert resp.status_code == 422
        assert resp.json()["error"] == "partner_ambiguous"
        assert await _tasks_count() == 0

    @pytest.mark.parametrize(
        "broken",
        [
            {"partner": {"inn": "12345"}},
            {"partner": {}},
            {"updated_at": "2026-11-27T10:00:00"},
            {"bitrix_url": "https://evil.example.com/task/1"},
            {"status": "unknown"},
            {"title": "   "},
        ],
    )
    async def test_invalid_payload_returns_400(self, client: AsyncClient, setup_db, broken):
        await _make_partner("a@test.com", INN_A, "Партнёр А")
        body = payload(**broken)

        resp = await client.post("/api/integration/tasks", json=body, headers=_headers())

        assert resp.status_code == 400, resp.text
        assert resp.json()["error"] == "invalid_payload"

    async def test_task_without_partner_is_not_created(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А")
        body = payload()
        body.pop("partner")

        resp = await client.post("/api/integration/tasks", json=body, headers=_headers())

        assert resp.status_code == 400
        assert await _tasks_count() == 0

    async def test_token_is_required(self, client: AsyncClient, setup_db):
        no_token = await client.post(
            "/api/integration/tasks",
            json=payload(),
            headers={"Idempotency-Key": "bitrix-18591"},
        )
        wrong = await client.post(
            "/api/integration/tasks",
            json=payload(),
            headers={"X-Integration-Token": "nope", "Idempotency-Key": "bitrix-18591"},
        )

        assert no_token.status_code == 401
        assert wrong.status_code == 401
        assert wrong.json()["error"] == "unauthorized"

    async def test_disabled_integration_returns_503(self, client: AsyncClient, setup_db, monkeypatch):
        monkeypatch.setattr(settings, "BITRIX_INTEGRATION_TOKEN", "")

        resp = await client.post("/api/integration/tasks", json=payload(), headers=_headers())

        assert resp.status_code == 503
        assert resp.json()["error"] == "integration_disabled"

    async def test_idempotency_key_is_required(self, client: AsyncClient, setup_db):
        resp = await client.post(
            "/api/integration/tasks",
            json=payload(),
            headers={"X-Integration-Token": TOKEN},
        )

        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_payload"

    async def test_partner_sees_only_own_task(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        user_b, _ = await _make_partner("b@test.com", INN_B, "Партнёр Б")
        created = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        task_id = created.json()["lkp_task_id"]

        own = await client.get(f"/api/v1/tasks/{task_id}", headers=auth(user_a))
        foreign = await client.get(f"/api/v1/tasks/{task_id}", headers=auth(user_b))
        listing = await client.get("/api/v1/tasks", headers=auth(user_b))

        assert own.status_code == 200
        assert own.json()["bitrix_author_name"] == "Евгений Самсонюк"
        assert own.json()["bitrix_client_name"] == "Савин Валерий Алексеевич"
        assert foreign.status_code == 404
        assert listing.json()["total"] == 0

    async def test_expired_deadline_is_shown_as_overdue(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        past = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        await client.post(
            "/api/integration/tasks",
            json=payload(deadline=past),
            headers=_headers(),
        )

        listing = await client.get("/api/v1/tasks?assigned_to=partner", headers=auth(user_a))

        assert listing.json()["items"][0]["status"] == "overdue"


class TestStatusChanges:
    async def test_partner_action_appears_in_feed(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        created = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        task_id = created.json()["lkp_task_id"]
        since = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

        action = await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "in_progress"},
            headers=auth(user_a),
        )
        feed = await client.get(
            "/api/integration/tasks/changes",
            params={"since": since},
            headers={"X-Integration-Token": TOKEN},
        )

        assert action.status_code == 200, action.text
        assert feed.status_code == 200
        items = feed.json()["items"]
        assert len(items) == 1
        assert items[0]["bitrix_task_id"] == 18591
        assert items[0]["lkp_task_id"] == task_id
        assert items[0]["status"] == "in_progress"
        assert items[0]["author_name"] == "Ангелина Савина"

    async def test_gateway_changes_are_not_echoed(self, client: AsyncClient, setup_db):
        await _make_partner("a@test.com", INN_A, "Партнёр А")
        await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        since = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

        feed = await client.get(
            "/api/integration/tasks/changes",
            params={"since": since},
            headers={"X-Integration-Token": TOKEN},
        )

        assert feed.json()["items"] == []

    async def test_reject_reason_is_passed_to_gateway(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        created = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        task_id = created.json()["lkp_task_id"]
        since = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

        await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "rejected", "reject_reason": "Нет доверенности от должника"},
            headers=auth(user_a),
        )
        feed = await client.get(
            "/api/integration/tasks/changes",
            params={"since": since},
            headers={"X-Integration-Token": TOKEN},
        )

        item = feed.json()["items"][0]
        assert item["status"] == "rejected"
        assert item["reject_reason"] == "Нет доверенности от должника"

    async def test_limit_and_next_since_paginate(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        created = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        task_id = created.json()["lkp_task_id"]
        since = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

        await client.post(f"/api/v1/tasks/{task_id}/status", json={"status": "in_progress"}, headers=auth(user_a))
        await client.post(f"/api/v1/tasks/{task_id}/status", json={"status": "done"}, headers=auth(user_a))

        first = await client.get(
            "/api/integration/tasks/changes",
            params={"since": since, "limit": 1},
            headers={"X-Integration-Token": TOKEN},
        )
        assert len(first.json()["items"]) == 1

        second = await client.get(
            "/api/integration/tasks/changes",
            params={"since": first.json()["next_since"], "limit": 1},
            headers={"X-Integration-Token": TOKEN},
        )
        assert len(second.json()["items"]) == 1
        # Пара (in_progress, done) не должна терять второе изменение.
        assert second.json()["items"][0]["status"] == "done"

    async def test_missing_since_returns_empty_feed(self, client: AsyncClient, setup_db):
        resp = await client.get(
            "/api/integration/tasks/changes",
            headers={"X-Integration-Token": TOKEN},
        )

        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["next_since"]

    async def test_feed_requires_token(self, client: AsyncClient, setup_db):
        resp = await client.get("/api/integration/tasks/changes?since=2026-11-27T10:00:00%2B03:00")

        assert resp.status_code == 401


class TestPartnerActions:
    async def _create(self, client: AsyncClient) -> str:
        created = await client.post("/api/integration/tasks", json=payload(), headers=_headers())
        assert created.status_code == 201, created.text
        return created.json()["lkp_task_id"]

    async def test_take_in_work(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        task_id = await self._create(client)

        resp = await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "in_progress"},
            headers=auth(user_a),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "in_progress"
        assert body["status_changed_at"]
        assert any(event["type"] == "status_changed" for event in body["events"])

    async def test_done_completes_task(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        task_id = await self._create(client)

        resp = await client.post(f"/api/v1/tasks/{task_id}/status", json={"status": "done"}, headers=auth(user_a))

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_at"]

    async def test_reject_requires_reason(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        task_id = await self._create(client)

        resp = await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "rejected"},
            headers=auth(user_a),
        )

        assert resp.status_code == 422

    async def test_reject_stores_reason_and_notifies_manager(self, client: AsyncClient, setup_db):
        from sqlalchemy import select

        from app.models.notification import Notification
        from tests.conftest import async_session_test

        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        admin_id = await _make_admin()
        task_id = await self._create(client)

        resp = await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "rejected", "reject_reason": "Нет доверенности"},
            headers=auth(user_a),
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["reject_reason"] == "Нет доверенности"
        async with async_session_test() as session:
            notes = (
                await session.scalars(select(Notification).where(Notification.user_id == uuid.UUID(admin_id)))
            ).all()
        assert any("отклонил" in note.title.lower() for note in notes)

    async def test_cannot_edit_task_fields(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        task_id = await self._create(client)

        resp = await client.put(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Свой заголовок"},
            headers=auth(user_a),
        )

        assert resp.status_code == 400

    async def test_foreign_partner_gets_404(self, client: AsyncClient, setup_db):
        _, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        user_b, _ = await _make_partner("b@test.com", INN_B, "Партнёр Б")
        task_id = await self._create(client)

        resp = await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "in_progress"},
            headers=auth(user_b),
        )

        assert resp.status_code == 404

    async def test_status_is_idempotent(self, client: AsyncClient, setup_db):
        user_a, _ = await _make_partner("a@test.com", INN_A, "Партнёр А")
        task_id = await self._create(client)
        await client.post(f"/api/v1/tasks/{task_id}/status", json={"status": "in_progress"}, headers=auth(user_a))
        since = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

        again = await client.post(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "in_progress"},
            headers=auth(user_a),
        )
        feed = await client.get(
            "/api/integration/tasks/changes",
            params={"since": since},
            headers={"X-Integration-Token": TOKEN},
        )

        assert again.status_code == 200
        # Повторное нажатие не должно порождать второе изменение для шлюза.
        assert len(feed.json()["items"]) == 1
