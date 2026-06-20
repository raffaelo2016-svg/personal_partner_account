"""Дополнения к test_partner_settings: change-password корнеры.

settings_service.change_password сейчас проверяет только:
  - наличие юзера;
  - верность текущего пароля;
  - длину нового >= 8.

Тесты закрепляют это поведение (в том числе отсутствие проверок, которые могли бы
появиться «случайно» — они должны появляться вместе с явными тестами, не молча).
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.api_integration.conftest import auth

URL = "/api/v1/settings/change-password"


class TestChangePasswordCorners:
    async def test_wrong_current_returns_400(self, client: AsyncClient, partner_token):
        resp = await client.post(
            URL,
            json={"current_password": "wrong-one", "new_password": "NewPass123"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json().get("detail", "").lower()

    async def test_new_too_short_returns_400(self, client: AsyncClient, partner_token):
        resp = await client.post(
            URL,
            json={"current_password": "password123", "new_password": "short"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 400
        assert "8" in resp.json().get("detail", "")

    async def test_new_equal_to_current_is_allowed(self, client: AsyncClient, partner_token):
        """Сейчас НЕ запрещено менять пароль на такой же. Фиксируем — если решите
        добавить запрет, этот тест сломается и заставит явно обновить ожидание."""
        resp = await client.post(
            URL,
            json={"current_password": "password123", "new_password": "password123"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200

    async def test_access_token_still_valid_after_password_change(
        self,
        client: AsyncClient,
        partner_token,
    ):
        """Access JWT stateless — смена пароля не инвалидирует его до экспирации.
        Анти-регрессия: если кто-то добавит blacklist, тест сломается, и это будет
        осознанное изменение, а не тихий сюрприз."""
        resp = await client.post(
            URL,
            json={"current_password": "password123", "new_password": "AnotherPass9"},
            headers=auth(partner_token),
        )
        assert resp.status_code == 200

        # Тот же access-токен — всё ещё работает на /me
        me = await client.get("/api/v1/auth/me", headers=auth(partner_token))
        assert me.status_code == 200

    async def test_missing_body_422(self, client: AsyncClient, partner_token):
        resp = await client.post(URL, json={}, headers=auth(partner_token))
        assert resp.status_code == 422

    async def test_no_auth_rejected(self, client: AsyncClient):
        resp = await client.post(
            URL,
            json={"current_password": "password123", "new_password": "NewPass123"},
        )
        assert resp.status_code in (401, 403)
