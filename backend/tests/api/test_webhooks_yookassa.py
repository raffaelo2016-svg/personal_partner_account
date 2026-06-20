"""API-тесты: /api/v1/webhooks/yookassa.

handle_yookassa_event мокается, реально БД не дёргается. Проверяем сам контракт ручки
(IP-чек, валидация payload, обработка исключений).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings

URL = "/api/v1/webhooks/yookassa"


async def _noop(*args, **kwargs):
    return None


class TestValidPayload:
    async def test_payment_succeeded_returns_ok(self, client: AsyncClient, monkeypatch):
        called = {}

        async def fake_handler(db, event, payment_id):
            called["event"] = event
            called["payment_id"] = payment_id

        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", fake_handler)
        resp = await client.post(
            URL,
            json={"event": "payment.succeeded", "object": {"id": "pmt-123"}},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True}
        assert called == {"event": "payment.succeeded", "payment_id": "pmt-123"}

    async def test_payment_canceled_routed(self, client: AsyncClient, monkeypatch):
        seen_events = []

        async def fake_handler(db, event, payment_id):
            seen_events.append(event)

        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", fake_handler)
        resp = await client.post(
            URL,
            json={"event": "payment.canceled", "object": {"id": "pmt-xyz"}},
        )
        assert resp.status_code == 200
        assert seen_events == ["payment.canceled"]

    async def test_repeated_calls_same_payment_idempotent(self, client: AsyncClient, monkeypatch):
        """Ручка не ломается от повторной доставки — handler вызывается дважды."""
        count = {"n": 0}

        async def fake_handler(db, event, payment_id):
            count["n"] += 1

        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", fake_handler)
        payload = {"event": "payment.succeeded", "object": {"id": "pmt-dup"}}
        r1 = await client.post(URL, json=payload)
        r2 = await client.post(URL, json=payload)
        assert r1.status_code == 200 and r2.status_code == 200
        assert count["n"] == 2


class TestInvalidPayload:
    async def test_invalid_json(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(URL, content=b"not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid JSON"

    async def test_missing_event(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(URL, json={"object": {"id": "pmt-1"}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid payload"

    async def test_missing_object_id(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(URL, json={"event": "payment.succeeded", "object": {}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid payload"

    async def test_missing_object_entirely(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(URL, json={"event": "payment.succeeded"})
        assert resp.status_code == 400

    async def test_null_object(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(URL, json={"event": "payment.succeeded", "object": None})
        assert resp.status_code == 400


class TestHandlerErrors:
    async def test_handler_exception_returns_500(self, client: AsyncClient, monkeypatch):
        async def boom(db, event, payment_id):
            raise RuntimeError("db is down")

        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", boom)
        resp = await client.post(
            URL,
            json={"event": "payment.succeeded", "object": {"id": "pmt-err"}},
        )
        assert resp.status_code == 500
        body = resp.json()
        # Generic message — no traceback / exception class leaked to client.
        assert body == {"detail": "Webhook processing failed"}
        assert "traceback" not in body
        assert "RuntimeError" not in body["detail"]


class TestIpEnforcement:
    async def test_production_rejects_non_yookassa_ip(self, client: AsyncClient, monkeypatch):
        """В production IP, не из allow-list, → 403 Forbidden."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr("app.api.webhooks.is_yookassa_ip", lambda ip: False)
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(
            URL,
            json={"event": "payment.succeeded", "object": {"id": "pmt-blocked"}},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Forbidden"

    async def test_production_allows_yookassa_ip(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr("app.api.webhooks.is_yookassa_ip", lambda ip: True)
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(
            URL,
            json={"event": "payment.succeeded", "object": {"id": "pmt-ok"}},
        )
        assert resp.status_code == 200

    async def test_development_bypasses_ip_check(self, client: AsyncClient, monkeypatch):
        """В dev IP-проверка пропускается, даже если is_yookassa_ip вернул бы False."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr("app.api.webhooks.is_yookassa_ip", lambda ip: False)
        monkeypatch.setattr("app.api.webhooks.handle_yookassa_event", _noop)
        resp = await client.post(
            URL,
            json={"event": "payment.succeeded", "object": {"id": "pmt-dev"}},
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("env", ["production", "staging"])
    async def test_ip_enforced_in_prod_like_envs(self, client: AsyncClient, monkeypatch, env):
        monkeypatch.setattr(settings, "ENVIRONMENT", env)
        monkeypatch.setattr("app.api.webhooks.is_yookassa_ip", lambda ip: False)
        resp = await client.post(
            URL,
            json={"event": "payment.succeeded", "object": {"id": "pmt-x"}},
        )
        assert resp.status_code == 403
