"""Тесты персональных учётных записей администраторов."""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services import admin_access_service as access

PASSWORD = "Password1234"


async def _make_super(db, email="root@test.ru", login="root"):
    user = User(
        email=email,
        login=login,
        hashed_password=hash_password(PASSWORD),
        role="super_admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _make_admin(db, email="admin@test.ru", login="admin"):
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


async def _login(client, identifier: str, password: str = PASSWORD) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _bootstrap_key(db) -> str:
    token, _ = await access.create_bootstrap_key(db)
    await db.commit()
    return token


@pytest.mark.asyncio
async def test_setup_status_and_bootstrap(client, db_session):
    status = await client.get("/api/v1/setup/status")
    assert status.json() == {"needs_setup": True}

    key = await _bootstrap_key(db_session)
    resp = await client.post(
        "/api/v1/setup/bootstrap",
        json={"key": key, "email": "boss@test.ru", "login": "Boss", "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text

    status = await client.get("/api/v1/setup/status")
    assert status.json() == {"needs_setup": False}

    # ключ одноразовый
    again = await client.post(
        "/api/v1/setup/bootstrap",
        json={"key": key, "email": "boss2@test.ru", "login": "boss2", "password": PASSWORD},
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_invite_flow_and_login_by_login_or_email(client, db_session):
    boss = await _make_super(db_session)
    headers = await _login(client, "root")

    created = await client.post(
        "/api/v1/admin/invites",
        json={"email": "new.admin@test.ru", "role": "admin", "ttl_hours": 72},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["status"] == "active"
    assert payload["invite_url"]
    token = payload["invite_url"].rsplit("/", 1)[-1]

    info = await client.get(f"/api/v1/auth/invite/{token}")
    assert info.status_code == 200
    assert info.json()["email"] == "new.admin@test.ru"
    assert info.json()["inviter_label"] == boss.email

    registered = await client.post(
        "/api/v1/auth/invite/register",
        json={"token": token, "login": "New.Admin", "password": PASSWORD},
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["user"]["role"] == "admin"
    assert registered.json()["user"]["login"] == "new.admin"

    # вход по логину (регистр не важен) и по почте
    await _login(client, "new.admin")
    await _login(client, "NEW.ADMIN@TEST.RU")

    # повторное использование ссылки
    again = await client.post(
        "/api/v1/auth/invite/register",
        json={"token": token, "login": "another", "password": PASSWORD},
    )
    assert again.status_code == 410


@pytest.mark.asyncio
async def test_plain_admin_cannot_manage_access(client, db_session):
    await _make_super(db_session)
    await _make_admin(db_session, email="plain@test.ru", login="plain")
    headers = await _login(client, "plain")

    resp = await client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/admin/invites",
        json={"email": "x@test.ru", "role": "admin", "ttl_hours": 72},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_block_and_unblock(client, db_session):
    await _make_super(db_session)
    admin = await _make_admin(db_session, email="blocked@test.ru", login="blocked")
    headers = await _login(client, "root")

    blocked = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"is_active": False},
        headers=headers,
    )
    assert blocked.status_code == 200
    assert blocked.json()["is_active"] is False

    login_attempt = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "blocked", "password": PASSWORD},
    )
    assert login_attempt.status_code == 401

    unblocked = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"is_active": True},
        headers=headers,
    )
    assert unblocked.status_code == 200
    await _login(client, "blocked")


@pytest.mark.asyncio
async def test_cannot_block_self_or_last_super_admin(client, db_session):
    boss = await _make_super(db_session)
    headers = await _login(client, "root")

    self_block = await client.patch(
        f"/api/v1/admin/users/{boss.id}",
        json={"is_active": False},
        headers=headers,
    )
    assert self_block.status_code == 400

    other = await _make_super(db_session, email="second@test.ru", login="second")
    demote_other = await client.patch(
        f"/api/v1/admin/users/{other.id}",
        json={"role": "admin"},
        headers=headers,
    )
    assert demote_other.status_code == 200

    # остался один супер-админ — понизить его нельзя
    demote_last = await client.patch(
        f"/api/v1/admin/users/{boss.id}",
        json={"role": "admin"},
        headers=headers,
    )
    assert demote_last.status_code == 400


@pytest.mark.asyncio
async def test_invite_expired_and_revoked(client, db_session):
    await _make_super(db_session)
    headers = await _login(client, "root")

    created = await client.post(
        "/api/v1/admin/invites",
        json={"email": "late@test.ru", "role": "admin", "ttl_hours": 24},
        headers=headers,
    )
    invite_id = created.json()["id"]
    token = created.json()["invite_url"].rsplit("/", 1)[-1]

    revoked = await client.delete(f"/api/v1/admin/invites/{invite_id}", headers=headers)
    assert revoked.status_code == 200

    info = await client.get(f"/api/v1/auth/invite/{token}")
    assert info.json()["status"] == "revoked"

    resp = await client.post(
        "/api/v1/auth/invite/register",
        json={"token": token, "login": "latecomer", "password": PASSWORD},
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_invite_rejects_taken_email_and_weak_password(client, db_session):
    await _make_super(db_session)
    await _make_admin(db_session, email="taken@test.ru", login="taken")
    headers = await _login(client, "root")

    dup = await client.post(
        "/api/v1/admin/invites",
        json={"email": "taken@test.ru", "role": "admin", "ttl_hours": 72},
        headers=headers,
    )
    assert dup.status_code == 409

    created = await client.post(
        "/api/v1/admin/invites",
        json={"email": "weak@test.ru", "role": "admin", "ttl_hours": 72},
        headers=headers,
    )
    token = created.json()["invite_url"].rsplit("/", 1)[-1]

    weak = await client.post(
        "/api/v1/auth/invite/register",
        json={"token": token, "login": "weakuser", "password": "short1"},
    )
    assert weak.status_code == 400
    assert weak.json()["detail"]["code"] == "WEAK_PASSWORD"


@pytest.mark.asyncio
async def test_audit_page_returns_events(client, db_session):
    await _make_super(db_session)
    headers = await _login(client, "root")
    await client.post(
        "/api/v1/admin/invites",
        json={"email": "audit@test.ru", "role": "admin", "ttl_hours": 72},
        headers=headers,
    )

    resp = await client.get("/api/v1/admin/audit?page_size=50", headers=headers)
    assert resp.status_code == 200
    actions = {item["action"] for item in resp.json()["items"]}
    assert "invite_created" in actions


@pytest.mark.asyncio
async def test_shared_account_disabled_and_bulk_invites(client, db_session):
    shared = User(
        email="shared@test.ru",
        login=None,
        hashed_password=hash_password(PASSWORD),
        role="admin",
        is_active=True,
    )
    db_session.add(shared)
    await db_session.commit()

    boss = await _make_super(db_session)
    found = await access.find_shared_admin(db_session)
    assert found is not None and found.id == shared.id

    created, failed = await access.bulk_invite(
        db_session,
        emails=["one@test.ru", "two@test.ru", "root@test.ru"],
        role="admin",
        actor=boss,
        ttl_hours=72,
    )
    await db_session.commit()

    assert len(created) == 2
    assert failed and failed[0][0] == "root@test.ru"

    await access.disable_shared_admin(db_session, shared, actor_label="test")
    await db_session.commit()

    refreshed = await db_session.get(User, shared.id)
    assert refreshed.is_active is False
    assert refreshed.is_legacy_shared is True

    login_attempt = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "shared@test.ru", "password": PASSWORD},
    )
    assert login_attempt.status_code == 401


@pytest.mark.asyncio
async def test_invite_link_can_be_copied_from_list(client, db_session):
    await _make_super(db_session)
    headers = await _login(client, "root")

    created = await client.post(
        "/api/v1/admin/invites",
        json={"email": "copy@test.ru", "role": "admin", "ttl_hours": 72},
        headers=headers,
    )
    assert created.status_code == 201

    listed = await client.get("/api/v1/admin/invites", headers=headers)
    assert listed.status_code == 200
    item = next(i for i in listed.json() if i["email"] == "copy@test.ru")
    assert item["invite_url"], "ссылка должна оставаться доступной из списка"

    # после использования ссылка из списка исчезает
    token = item["invite_url"].rsplit("/", 1)[-1]
    registered = await client.post(
        "/api/v1/auth/invite/register",
        json={"token": token, "login": "copied", "password": PASSWORD},
    )
    assert registered.status_code == 201

    listed_after = await client.get("/api/v1/admin/invites", headers=headers)
    used = next(i for i in listed_after.json() if i["email"] == "copy@test.ru")
    assert used["status"] == "used"
    assert not used["invite_url"]
