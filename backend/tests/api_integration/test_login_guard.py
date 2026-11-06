"""Капча и временная блокировка после неудачных входов."""

import pytest

from app.config import settings
from app.core.redis import redis_client
from app.core.security import hash_password
from app.models.user import User
from app.services import captcha_service, login_guard

PASSWORD = "Password1234"


@pytest.fixture(autouse=True)
async def _clean_redis():
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


async def _make_admin(db, email="guard@test.ru", login="guard"):
    user = User(
        email=email,
        login=login,
        hashed_password=hash_password(PASSWORD),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _login(client, password=PASSWORD, captcha_token=None):
    payload = {"identifier": "guard", "password": password}
    if captcha_token:
        payload["captcha_token"] = captcha_token
    return await client.post("/api/v1/auth/login", json=payload)


@pytest.mark.asyncio
async def test_captcha_required_after_three_failures(client, db_session, monkeypatch):
    await _make_admin(db_session)
    monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-key")

    for _ in range(3):
        assert (await _login(client, password="WrongPass123")).status_code == 401

    blocked = await _login(client)
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "CAPTCHA_REQUIRED"

    async def fake_verify(token: str, ip: str | None = None) -> bool:
        return token == "good-token"

    monkeypatch.setattr(captcha_service, "verify_captcha", fake_verify)

    bad = await _login(client, captcha_token="bad-token")
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "CAPTCHA_INVALID"

    ok = await _login(client, captcha_token="good-token")
    assert ok.status_code == 200

    # успешный вход сбрасывает счётчик
    again = await _login(client)
    assert again.status_code == 200


@pytest.mark.asyncio
async def test_lockout_after_five_failures(client, db_session, monkeypatch):
    await _make_admin(db_session)
    monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-key")

    async def fake_verify(token: str, ip: str | None = None) -> bool:
        return token == "good-token"

    monkeypatch.setattr(captcha_service, "verify_captcha", fake_verify)

    for _ in range(3):
        assert (await _login(client, password="WrongPass123")).status_code == 401

    # с 4-й попытки уже нужна капча, но пароль по-прежнему неверный
    assert (await _login(client, password="WrongPass123")).json()["detail"]["code"] == "CAPTCHA_REQUIRED"
    assert (await _login(client, password="WrongPass123", captcha_token="good-token")).status_code == 401
    assert (await _login(client, password="WrongPass123", captcha_token="good-token")).status_code == 401

    locked = await _login(client)
    assert locked.status_code == 429
    assert locked.json()["detail"]["code"] == "ACCOUNT_LOCKED"

    # даже верный пароль не проходит, пока блокировка активна
    still_locked = await _login(client, password=PASSWORD, captcha_token="good-token")
    assert still_locked.status_code == 429


@pytest.mark.asyncio
async def test_no_captcha_when_disabled(client, db_session, monkeypatch):
    await _make_admin(db_session)
    monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "")

    for _ in range(3):
        assert (await _login(client, password="WrongPass123")).status_code == 401

    # без настроенной капчи вход по верному паролю разрешён
    ok = await _login(client)
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_counter_is_shared_by_ip_and_identifier(client, db_session, monkeypatch):
    await _make_admin(db_session)
    monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-key")

    for _ in range(3):
        await _login(client, password="WrongPass123")

    assert await login_guard.get_failures("guard", "127.0.0.1") == 3
    # другой логин тем же IP не блокируется этим счётчиком
    other = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "someone@test.ru", "password": "WrongPass123"},
    )
    assert other.status_code == 401
