"""Тесты агентского кабинета: регистрация, привязка, начисления, выплаты."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.agent import Agent, AgentAccrual, AgentPayoutRequest
from app.models.client import Client
from app.models.notification import Notification
from app.models.partner import Partner
from app.models.user import User
from app.services import agent_service
from app.services.status_machine import change_status

PASSWORD = "Password1234"


async def _login(client, identifier: str, password: str = PASSWORD) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _register_agent(client, email="agent@test.ru", name="Пётр Агентов"):
    resp = await client.post(
        "/api/v1/auth/register-agent",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": name,
            "phone": "+79000000000",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_admin(db, email="root@test.ru", login="root") -> User:
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


async def _make_partner(db, email="partner@test.ru", company="ООО Партнёр", agent_code=None) -> Partner:
    user = User(
        email=email,
        login=email.split("@")[0],
        hashed_password=hash_password(PASSWORD),
        role="partner",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    partner = Partner(
        user_id=user.id,
        partner_type="legal",
        company_name=company,
        director_name="Иванов Иван",
        inn="",
        phone="+79000000000",
        status="active",
    )
    db.add(partner)
    await db.flush()
    if agent_code:
        await agent_service.link_partner_by_code(db, partner, agent_code)
    await db.commit()
    return partner


@pytest.mark.asyncio
async def test_agent_registration_creates_profile(client, db_session):
    data = await _register_agent(client)
    assert data["user"]["role"] == "agent"

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = await client.get("/api/v1/agent/me", headers=headers)
    assert me.status_code == 200, me.text
    profile = me.json()["profile"]
    assert profile["code"]
    assert profile["referral_link"].endswith(profile["code"])
    assert me.json()["stats"]["available"] == 0

    agent = (await db_session.execute(select(Agent))).scalar_one()
    assert agent.user_id is not None


@pytest.mark.asyncio
async def test_partner_registration_by_referral_code_links_agent(client, db_session):
    await _register_agent(client)
    agent = (await db_session.execute(select(Agent))).scalar_one()

    linked = await _make_partner(db_session, email="p1@test.ru", company="ООО Один", agent_code=agent.code)
    assert linked.agent_id == agent.id

    plain = await _make_partner(db_session, email="p2@test.ru", company="ООО Два")
    assert plain.agent_id is None

    # несуществующий код не ломает регистрацию и ничего не закрепляет
    invalid = await _make_partner(db_session, email="p3@test.ru", company="ООО Три", agent_code="ZZZZZZZZ")
    assert invalid.agent_id is None


@pytest.mark.asyncio
async def test_accrual_on_procedure_started_once(client, db_session):
    reg = await _register_agent(client)
    agent = (await db_session.execute(select(Agent))).scalar_one()
    admin = await _make_admin(db_session)
    partner = await _make_partner(db_session, agent_code=agent.code)

    client_row = Client(
        partner_id=partner.id,
        type="in_court",
        full_name="Клиент Тестовый",
        status="waiting_hearing",
    )
    db_session.add(client_row)
    await db_session.commit()

    await change_status(db_session, str(client_row.id), "restructuring", user_id=str(admin.id))
    await db_session.commit()

    accruals = (await db_session.execute(select(AgentAccrual))).scalars().all()
    assert len(accruals) == 1
    assert accruals[0].amount == 100000
    assert accruals[0].status == "accrued"

    # повторное событие не создаёт второе начисление
    await agent_service.accrue_for_client(db_session, client_row)
    await db_session.commit()
    again = (await db_session.execute(select(AgentAccrual))).scalars().all()
    assert len(again) == 1

    headers = {"Authorization": f"Bearer {reg['access_token']}"}
    stats = (await client.get("/api/v1/agent/me", headers=headers)).json()["stats"]
    assert stats["partners"] == 1
    assert stats["clients"] == 1
    assert stats["accrued"] == 100000
    assert stats["available"] == 100000


@pytest.mark.asyncio
async def test_payout_requires_requisites_and_blocks_double_request(client, db_session):
    reg = await _register_agent(client)
    agent = (await db_session.execute(select(Agent))).scalar_one()
    await _make_admin(db_session)
    partner = await _make_partner(db_session, agent_code=agent.code)

    client_row = Client(partner_id=partner.id, type="in_court", full_name="Клиент", status="waiting_hearing")
    db_session.add(client_row)
    await db_session.commit()
    await agent_service.accrue_for_client(db_session, client_row)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    blocked = await client.post("/api/v1/agent/payouts", headers=headers)
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "REQUISITES_NOT_ACCEPTED"

    req = await client.put(
        "/api/v1/agent/requisites",
        headers=headers,
        json={"recipient_type": "individual", "data": {"fio": "Пётр Агентов", "account": "40817"}},
    )
    assert req.status_code == 200
    assert req.json()["requisites_status"] == "sent"

    admin_headers = await _login(client, "root")
    accepted = await client.patch(
        f"/api/v1/admin/agents/{agent.id}/requisites",
        headers=admin_headers,
        json={"status": "accepted"},
    )
    assert accepted.status_code == 200

    created = await client.post("/api/v1/agent/payouts", headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["amount"] == 100000
    assert created.json()["status"] == "submitted"

    second = await client.post("/api/v1/agent/payouts", headers=headers)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "PAYOUT_EXISTS"

    # админ подтверждает выплату
    payout_id = created.json()["id"]
    paid = await client.patch(
        f"/api/v1/admin/payouts/{payout_id}",
        headers=admin_headers,
        json={"status": "paid", "comment": "Переведено 15-го"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_at"] is not None

    rows = (await db_session.execute(select(AgentPayoutRequest))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_admin_can_rebind_partner_with_reason(client, db_session):
    reg1 = await _register_agent(client, email="a1@test.ru", name="Агент Один")
    await _register_agent(client, email="a2@test.ru", name="Агент Два")
    agents = (await db_session.execute(select(Agent).order_by(Agent.full_name))).scalars().all()
    first, second = agents[0], agents[1]

    await _make_admin(db_session)
    partner = await _make_partner(db_session, agent_code=first.code)
    admin_headers = await _login(client, "root")

    denied = await client.post(
        f"/api/v1/admin/partners/{partner.id}/agent",
        headers=admin_headers,
        json={"agent_id": str(second.id), "reason": "Ошибка привязки"},
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "PARTNER_ALREADY_LINKED"

    moved = await client.post(
        f"/api/v1/admin/partners/{partner.id}/agent",
        headers=admin_headers,
        json={"agent_id": str(second.id), "reason": "Ошибка привязки", "force": True},
    )
    assert moved.status_code == 200
    assert moved.json()["id"] == str(second.id)

    listed = await client.get("/api/v1/admin/agents", headers=admin_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    detail = await client.get(f"/api/v1/admin/agents/{second.id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["agent"]["stats"]["partners"] == 1

    assert reg1["access_token"]


@pytest.mark.asyncio
async def test_partner_registration_api_passes_agent_code(client, db_session):
    await _register_agent(client, email="ref@test.ru", name="Реф Агент")
    agent = (await db_session.execute(select(Agent))).scalar_one()

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newpartner@test.ru",
            "password": PASSWORD,
            "agent_code": agent.code,
            "partner_type": "individual",
            "region": "Москва",
            "company_name": "ИП Новый Партнёр",
            "director_name": "Новый Партнёр",
            "inn": "",
            "phone": "+79001112233",
        },
    )
    assert resp.status_code == 201, resp.text

    partner = (await db_session.execute(select(Partner).where(Partner.company_name == "ИП Новый Партнёр"))).scalar_one()
    assert partner.agent_id == agent.id
    assert partner.agent_linked_at is not None


@pytest.mark.asyncio
async def test_agent_invite_creates_agent_profile(client, db_session):
    await _make_admin(db_session)
    admin_headers = await _login(client, "root")

    invite = await client.post(
        "/api/v1/admin/invites",
        headers=admin_headers,
        json={"email": "invited.agent@test.ru", "role": "agent", "ttl_hours": 72},
    )
    assert invite.status_code == 201, invite.text
    assert invite.json()["role"] == "agent"

    token = invite.json()["invite_url"].rsplit("/", 1)[-1]
    registered = await client.post(
        "/api/v1/auth/invite/register",
        json={
            "token": token,
            "login": "invagent",
            "password": PASSWORD,
            "full_name": "Приглашённый Агент",
            "phone": "+79001234567",
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["user"]["role"] == "agent"

    agent = (await db_session.execute(select(Agent).where(Agent.full_name == "Приглашённый Агент"))).scalar_one()
    assert agent.phone == "+79001234567"

    me = await client.get(
        "/api/v1/agent/me",
        headers={"Authorization": f"Bearer {registered.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["profile"]["code"] == agent.code


@pytest.mark.asyncio
async def test_agent_receives_notifications(client, db_session):
    reg = await _register_agent(client, email="notify@test.ru", name="Агент Уведомлений")
    agent = (await db_session.execute(select(Agent))).scalar_one()
    await _make_admin(db_session)
    partner = await _make_partner(db_session, email="np@test.ru", agent_code=agent.code)

    client_row = Client(partner_id=partner.id, type="in_court", full_name="Клиент", status="waiting_hearing")
    db_session.add(client_row)
    await db_session.commit()
    await agent_service.accrue_for_client(db_session, client_row)
    await db_session.commit()

    agent_headers = {"Authorization": f"Bearer {reg['access_token']}"}
    admin_headers = await _login(client, "root")

    async def note_types() -> list[str]:
        rows = (
            (await db_session.execute(select(Notification).where(Notification.user_id == agent.user_id)))
            .scalars()
            .all()
        )
        return [n.type for n in rows]

    assert "agent_accrual" in await note_types()

    await client.put(
        "/api/v1/agent/requisites",
        headers=agent_headers,
        json={"recipient_type": "individual", "data": {"fio": "Агент", "account": "40817"}},
    )
    await client.patch(
        f"/api/v1/admin/agents/{agent.id}/requisites",
        headers=admin_headers,
        json={"status": "accepted"},
    )
    assert "agent_requisites" in await note_types()

    payout = await client.post("/api/v1/agent/payouts", headers=agent_headers)
    assert payout.status_code == 201
    await client.patch(
        f"/api/v1/admin/payouts/{payout.json()['id']}",
        headers=admin_headers,
        json={"status": "paid"},
    )
    assert "agent_payout" in await note_types()

    unread = await client.get("/api/v1/notifications/unread-count", headers=agent_headers)
    assert unread.status_code == 200
    assert unread.json()["count"] >= 3


@pytest.mark.asyncio
async def test_admin_corrects_accrual_with_reason(client, db_session):
    reg = await _register_agent(client, email="correct@test.ru", name="Агент Корректировок")
    agent = (await db_session.execute(select(Agent))).scalar_one()
    await _make_admin(db_session)
    partner = await _make_partner(db_session, email="cp@test.ru", agent_code=agent.code)

    client_row = Client(partner_id=partner.id, type="in_court", full_name="Клиент", status="waiting_hearing")
    db_session.add(client_row)
    await db_session.commit()
    accrual = await agent_service.accrue_for_client(db_session, client_row)
    await db_session.commit()

    admin_headers = await _login(client, "root")
    agent_headers = {"Authorization": f"Bearer {reg['access_token']}"}

    cancelled = await client.patch(
        f"/api/v1/admin/accruals/{accrual.id}",
        headers=admin_headers,
        json={"status": "cancelled", "reason": "Дубль дела"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["comment"] == "Дубль дела"

    stats = (await client.get("/api/v1/agent/me", headers=agent_headers)).json()["stats"]
    assert stats["accrued"] == 0
    assert stats["available"] == 0

    restored = await client.patch(
        f"/api/v1/admin/accruals/{accrual.id}",
        headers=admin_headers,
        json={"status": "accrued", "reason": "Проверили, дело в работе"},
    )
    assert restored.status_code == 200
    stats = (await client.get("/api/v1/agent/me", headers=agent_headers)).json()["stats"]
    assert stats["available"] == 100000

    failed = await client.patch(
        f"/api/v1/admin/accruals/{accrual.id}",
        headers=admin_headers,
        json={"status": "cancelled", "reason": "ok"},
    )
    assert failed.status_code == 422

    audit = await client.get(
        "/api/v1/admin/audit",
        headers=admin_headers,
        params={"action": "agent_accrual_corrected"},
    )
    assert audit.status_code == 200
    assert audit.json()["total"] >= 2
