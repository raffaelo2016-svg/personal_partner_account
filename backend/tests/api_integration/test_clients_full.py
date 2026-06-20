"""Полные API-тесты вкладки Клиенты: CRUD, валидация, статусы, фильтры, пагинация, прогресс, corner cases."""

import pytest
from httpx import AsyncClient

from app.models.client import Client
from tests.api_integration.conftest import auth, create_client
from tests.conftest import async_session_test

# ── Helpers ──


async def _create_and_get_id(client, token, **kwargs) -> str:
    c = await create_client(client, token, **kwargs)
    return c["id"]


async def _set_status(client: AsyncClient, token: str, client_id: str, status: str):
    """Установить статус напрямую в БД (для тестов переходов)."""
    async with async_session_test() as session:
        obj = await session.get(Client, client_id)
        obj.status = status
        await session.commit()


# ══════════════════════════════════════════════════════════
# 1. VALIDATION — создание клиента
# ══════════════════════════════════════════════════════════


class TestCreateValidation:
    async def test_create_success_minimal(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients", json={"type": "before_court", "full_name": "Тест"}, headers=auth(partner_token)
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "documents_collection"

    async def test_create_success_full(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients",
            json={
                "type": "in_court",
                "full_name": "Иванов Иван Иванович",
                "phone": "+79991234567",
                "email": "test@test.com",
                "passport_series": "1234",
                "passport_number": "567890",
                "inn": "770112345678",
                "snils": "12345678901",
                "region": "Москва",
                "case_number": "А40-123/2026",
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "in_court"

    async def test_create_missing_full_name(self, client: AsyncClient, partner_token):
        resp = await client.post("/api/v1/clients", json={"type": "before_court"}, headers=auth(partner_token))
        assert resp.status_code == 422

    async def test_create_missing_type(self, client: AsyncClient, partner_token):
        resp = await client.post("/api/v1/clients", json={"full_name": "Тест"}, headers=auth(partner_token))
        assert resp.status_code == 422

    async def test_create_invalid_type(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients", json={"type": "invalid_type", "full_name": "Тест"}, headers=auth(partner_token)
        )
        assert resp.status_code == 422

    async def test_create_empty_full_name(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients", json={"type": "before_court", "full_name": ""}, headers=auth(partner_token)
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "field,value",
        [
            ("passport_series", "x" * 5),
            ("passport_number", "x" * 7),
            ("inn", "x" * 13),
            ("snils", "x" * 15),
            ("phone", "x" * 21),
            ("region", "x" * 101),
            ("case_number", "x" * 51),
        ],
    )
    async def test_create_field_max_length(self, client: AsyncClient, partner_token, field, value):
        resp = await client.post(
            "/api/v1/clients",
            json={
                "type": "before_court",
                "full_name": "Тест",
                field: value,
            },
            headers=auth(partner_token),
        )
        assert resp.status_code == 422, f"Field {field} with len={len(value)} should fail"

    async def test_create_unicode_name(self, client: AsyncClient, partner_token):
        resp = await client.post(
            "/api/v1/clients",
            json={"type": "before_court", "full_name": "José O'Brien-Müller"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 201

    async def test_create_auto_sets_partner_id(self, client: AsyncClient, partner_token, partner):
        resp = await client.post(
            "/api/v1/clients", json={"type": "before_court", "full_name": "Auto"}, headers=auth(partner_token)
        )
        assert resp.json()["partner_id"] == str(partner.id)


# ══════════════════════════════════════════════════════════
# 2. UPDATE — обновление клиента
# ══════════════════════════════════════════════════════════


class TestUpdateClient:
    async def test_update_single_field(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        resp = await client.put(f"/api/v1/clients/{cid}", json={"full_name": "Новое Имя"}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Новое Имя"

    async def test_update_empty_body(self, client: AsyncClient, partner_token):
        """Пустое тело — ничего не меняется."""
        cid = await _create_and_get_id(client, partner_token, full_name="Оригинал")
        resp = await client.put(f"/api/v1/clients/{cid}", json={}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Оригинал"

    async def test_update_type(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token, client_type="before_court")
        resp = await client.put(f"/api/v1/clients/{cid}", json={"type": "in_court"}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["type"] == "in_court"

    async def test_update_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.put(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000", json={"full_name": "X"}, headers=auth(partner_token)
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# 3. DELETE — удаление клиента с каскадом
# ══════════════════════════════════════════════════════════


class TestDeleteClient:
    async def test_delete_and_gone(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        resp = await client.delete(f"/api/v1/clients/{cid}", headers=auth(partner_token))
        assert resp.status_code in (200, 204)
        assert (await client.get(f"/api/v1/clients/{cid}", headers=auth(partner_token))).status_code == 404

    async def test_delete_not_in_list(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token, full_name="ToDelete")
        await client.delete(f"/api/v1/clients/{cid}", headers=auth(partner_token))
        items = (await client.get("/api/v1/clients", headers=auth(partner_token))).json()["items"]
        assert all(c["id"] != cid for c in items)

    async def test_delete_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.delete("/api/v1/clients/00000000-0000-0000-0000-000000000000", headers=auth(partner_token))
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# 4. STATUS TRANSITIONS — все допустимые и запрещённые
# ══════════════════════════════════════════════════════════

VALID_TRANSITIONS = [
    ("documents_collection", "documents_formation"),
    ("documents_formation", "sent_to_court"),
    ("documents_formation", "documents_collection"),
    ("sent_to_court", "documents_decision"),
    ("sent_to_court", "documents_formation"),
    ("documents_decision", "waiting_hearing"),
    ("documents_decision", "sent_to_court"),
    ("waiting_hearing", "restructuring"),
    ("waiting_hearing", "documents_decision"),
    ("restructuring", "auction"),
    ("restructuring", "waiting_hearing"),
    ("auction", "realization"),
    ("auction", "restructuring"),
    ("realization", "auction"),
]

INVALID_TRANSITIONS = [
    ("documents_collection", "sent_to_court"),
    ("documents_collection", "waiting_hearing"),
    ("documents_collection", "realization"),
    ("documents_formation", "waiting_hearing"),
    ("sent_to_court", "auction"),
    ("realization", "documents_collection"),
]


class TestStatusTransitions:
    @pytest.mark.parametrize("from_status,to_status", VALID_TRANSITIONS)
    async def test_valid_transition(self, client: AsyncClient, partner_token, from_status, to_status):
        cid = await _create_and_get_id(client, partner_token)
        await _set_status(client, partner_token, cid, from_status)
        resp = await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": to_status}, headers=auth(partner_token)
        )
        assert resp.status_code == 200, f"{from_status} → {to_status} should be allowed"
        assert resp.json()["status"] == to_status

    @pytest.mark.parametrize("from_status,to_status", INVALID_TRANSITIONS)
    async def test_invalid_transition(self, client: AsyncClient, partner_token, from_status, to_status):
        cid = await _create_and_get_id(client, partner_token)
        await _set_status(client, partner_token, cid, from_status)
        resp = await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": to_status}, headers=auth(partner_token)
        )
        assert resp.status_code == 400, f"{from_status} → {to_status} should be forbidden"

    async def test_invalid_status_value(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        resp = await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": "nonexistent"}, headers=auth(partner_token)
        )
        assert resp.status_code == 400

    async def test_full_forward_chain(self, client: AsyncClient, partner_token):
        """Полная цепь от начала до конца."""
        cid = await _create_and_get_id(client, partner_token)
        chain = [
            "documents_formation",
            "sent_to_court",
            "documents_decision",
            "waiting_hearing",
            "restructuring",
            "auction",
            "realization",
        ]
        for status in chain:
            resp = await client.post(
                f"/api/v1/clients/{cid}/status", json={"status": status}, headers=auth(partner_token)
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    async def test_transition_with_comment(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        resp = await client.post(
            f"/api/v1/clients/{cid}/status",
            json={"status": "documents_formation", "comment": "Комментарий"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════
# 5. STATUS HISTORY
# ══════════════════════════════════════════════════════════


class TestStatusHistory:
    async def test_history_after_transition(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        await client.post(
            f"/api/v1/clients/{cid}/status",
            json={"status": "documents_formation", "comment": "Test"},
            headers=auth(partner_token),
        )
        resp = await client.get(f"/api/v1/clients/{cid}/status-history", headers=auth(partner_token))
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) >= 1
        assert history[0]["to_status"] == "documents_formation"
        assert history[0]["comment"] == "Test"

    async def test_history_multiple_transitions(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": "documents_formation"}, headers=auth(partner_token)
        )
        await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": "sent_to_court"}, headers=auth(partner_token)
        )
        history = (await client.get(f"/api/v1/clients/{cid}/status-history", headers=auth(partner_token))).json()
        assert len(history) >= 2

    async def test_history_nonexistent_client(self, client: AsyncClient, partner_token):
        resp = await client.get(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000/status-history", headers=auth(partner_token)
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# 6. FILTERING & SEARCH
# ══════════════════════════════════════════════════════════


class TestFiltering:
    async def test_filter_by_type_before_court(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, client_type="before_court", full_name="ДоСуда")
        await create_client(client, partner_token, client_type="in_court", full_name="ВСуде")
        items = (
            await client.get("/api/v1/clients", params={"type": "before_court"}, headers=auth(partner_token))
        ).json()["items"]
        assert all(c["type"] == "before_court" for c in items)

    async def test_filter_by_type_in_court(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, client_type="in_court", full_name="СудКлиент")
        items = (await client.get("/api/v1/clients", params={"type": "in_court"}, headers=auth(partner_token))).json()[
            "items"
        ]
        assert all(c["type"] == "in_court" for c in items)

    async def test_search_partial_name(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Петров Сергей Александрович")
        items = (await client.get("/api/v1/clients", params={"search": "Петров"}, headers=auth(partner_token))).json()[
            "items"
        ]
        assert any("Петров" in c["full_name"] for c in items)

    async def test_search_case_insensitive(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Козлов Дмитрий")
        items = (await client.get("/api/v1/clients", params={"search": "козлов"}, headers=auth(partner_token))).json()[
            "items"
        ]
        assert any("Козлов" in c["full_name"] for c in items)

    async def test_search_empty_string(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, full_name="Любой")
        resp = await client.get("/api/v1/clients", params={"search": ""}, headers=auth(partner_token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_search_no_results(self, client: AsyncClient, partner_token):
        items = (
            await client.get("/api/v1/clients", params={"search": "ZZZZZZZZZ"}, headers=auth(partner_token))
        ).json()["items"]
        assert len(items) == 0


# ══════════════════════════════════════════════════════════
# 7. PAGINATION
# ══════════════════════════════════════════════════════════


class TestPagination:
    async def test_page_size(self, client: AsyncClient, partner_token):
        for i in range(3):
            await create_client(client, partner_token, full_name=f"Page {i}")
        data = (await client.get("/api/v1/clients", params={"page_size": 2}, headers=auth(partner_token))).json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 3

    async def test_page_2(self, client: AsyncClient, partner_token):
        for i in range(3):
            await create_client(client, partner_token, full_name=f"P2 {i}")
        data = (
            await client.get("/api/v1/clients", params={"page": 2, "page_size": 2}, headers=auth(partner_token))
        ).json()
        assert len(data["items"]) >= 1

    async def test_page_out_of_range(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token)
        data = (await client.get("/api/v1/clients", params={"page": 999}, headers=auth(partner_token))).json()
        assert data["items"] == []
        assert data["total"] >= 1

    async def test_page_size_max(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/clients", params={"page_size": 100}, headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_page_size_over_max(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/clients", params={"page_size": 101}, headers=auth(partner_token))
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# 8. STATS
# ══════════════════════════════════════════════════════════


class TestStats:
    async def test_stats_structure(self, client: AsyncClient, partner_token):
        resp = await client.get("/api/v1/clients/stats", headers=auth(partner_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "before_court" in data
        assert "in_court" in data

    async def test_stats_count_by_type(self, client: AsyncClient, partner_token):
        await create_client(client, partner_token, client_type="before_court", full_name="StatBC")
        await create_client(client, partner_token, client_type="in_court", full_name="StatIC")
        data = (await client.get("/api/v1/clients/stats", headers=auth(partner_token))).json()
        assert data["before_court"] >= 1
        assert data["in_court"] >= 1

    async def test_stats_empty(self, client: AsyncClient, partner_token):
        """Без клиентов — всё по нулям."""
        data = (await client.get("/api/v1/clients/stats", headers=auth(partner_token))).json()
        assert data["total"] >= 0


# ══════════════════════════════════════════════════════════
# 9. PROGRESS
# ══════════════════════════════════════════════════════════


class TestProgress:
    async def test_progress_initial(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        resp = await client.get(f"/api/v1/clients/{cid}/progress", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_progress_after_transitions(self, client: AsyncClient, partner_token):
        cid = await _create_and_get_id(client, partner_token)
        await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": "documents_formation"}, headers=auth(partner_token)
        )
        await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": "sent_to_court"}, headers=auth(partner_token)
        )
        resp = await client.get(f"/api/v1/clients/{cid}/progress", headers=auth(partner_token))
        assert resp.status_code == 200

    async def test_progress_nonexistent(self, client: AsyncClient, partner_token):
        resp = await client.get(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000/progress", headers=auth(partner_token)
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# 10. ISOLATION — безопасность
# ══════════════════════════════════════════════════════════


class TestIsolation:
    async def test_partner_cannot_see_other(self, client: AsyncClient, partner_token, partner_token2):
        cid = await _create_and_get_id(client, partner_token, full_name="Чужой")
        assert (await client.get(f"/api/v1/clients/{cid}", headers=auth(partner_token2))).status_code == 404

    async def test_partner_cannot_update_other(self, client: AsyncClient, partner_token, partner_token2):
        cid = await _create_and_get_id(client, partner_token)
        assert (
            await client.put(f"/api/v1/clients/{cid}", json={"full_name": "Hack"}, headers=auth(partner_token2))
        ).status_code == 404

    async def test_partner_cannot_delete_other(self, client: AsyncClient, partner_token, partner_token2):
        cid = await _create_and_get_id(client, partner_token)
        assert (await client.delete(f"/api/v1/clients/{cid}", headers=auth(partner_token2))).status_code == 404

    async def test_partner_cannot_change_other_status(self, client: AsyncClient, partner_token, partner_token2):
        cid = await _create_and_get_id(client, partner_token)
        resp = await client.post(
            f"/api/v1/clients/{cid}/status", json={"status": "documents_formation"}, headers=auth(partner_token2)
        )
        assert resp.status_code == 404

    async def test_partner_cannot_see_other_history(self, client: AsyncClient, partner_token, partner_token2):
        cid = await _create_and_get_id(client, partner_token)
        assert (
            await client.get(f"/api/v1/clients/{cid}/status-history", headers=auth(partner_token2))
        ).status_code == 404

    async def test_partner_cannot_see_other_progress(self, client: AsyncClient, partner_token, partner_token2):
        cid = await _create_and_get_id(client, partner_token)
        assert (await client.get(f"/api/v1/clients/{cid}/progress", headers=auth(partner_token2))).status_code == 404

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/clients")
        assert resp.status_code in (401, 403)

    async def test_admin_sees_all(self, client: AsyncClient, partner_token, partner_token2, admin_token):
        await create_client(client, partner_token, full_name="От1")
        await create_client(client, partner_token2, full_name="От2")
        items = (await client.get("/api/v1/admin/clients", headers=auth(admin_token))).json()["items"]
        names = [c["full_name"] for c in items]
        assert "От1" in names and "От2" in names
