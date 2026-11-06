"""Список партнёров без клиентов: «не рабочие» и «затихшие»."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.core.security import hash_password
from app.models.client import Client
from app.models.partner import Partner
from app.models.user import User
from tests.api_integration.conftest import auth
from tests.conftest import async_session_test

API = "/api/v1/admin/partners/without-clients"
DASHBOARD = "/api/v1/admin/dashboard"


async def _make_partner(*, email: str, company: str, created_days_ago: int, status: str = "active") -> Partner:
    async with async_session_test() as session:
        user = User(email=email, hashed_password=hash_password("Partner123!"), role="partner", is_active=True)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        partner = Partner(
            user_id=user.id,
            company_name=company,
            director_name="Директор",
            inn="7701234567",
            phone="+71234567890",
            status=status,
            created_at=datetime.now(UTC) - timedelta(days=created_days_ago),
        )
        session.add(partner)
        await session.commit()
        await session.refresh(partner)
        return partner


async def _add_client(partner_id, *, created_days_ago: int) -> Client:
    async with async_session_test() as session:
        client_row = Client(
            partner_id=partner_id,
            type="before_court",
            full_name="Клиент Тестовый",
            created_at=datetime.now(UTC) - timedelta(days=created_days_ago),
        )
        session.add(client_row)
        await session.commit()
        await session.refresh(client_row)
        return client_row


async def _seed() -> dict[str, Partner]:
    never = await _make_partner(email="never@test.com", company="Никогда", created_days_ago=40)
    fresh = await _make_partner(email="fresh@test.com", company="Свежий", created_days_ago=5)

    stalled = await _make_partner(email="stalled@test.com", company="Затихший", created_days_ago=90)
    await _add_client(stalled.id, created_days_ago=45)

    alive = await _make_partner(email="alive@test.com", company="Живой", created_days_ago=90)
    await _add_client(alive.id, created_days_ago=3)

    blocked = await _make_partner(
        email="blocked@test.com",
        company="Заблокированный",
        created_days_ago=90,
        status="blocked",
    )
    return {"never": never, "fresh": fresh, "stalled": stalled, "alive": alive, "blocked": blocked}


async def _list(client: AsyncClient, token: str, mode: str, **params) -> dict:
    resp = await client.get(API, params={"mode": mode, **params}, headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestPartnersWithoutClients:
    async def test_no_clients_only_never_transmitted(self, client: AsyncClient, admin_token):
        seeded = await _seed()

        data = await _list(client, admin_token, "no_clients")
        ids = {item["id"] for item in data["items"]}

        assert str(seeded["never"].id) in ids
        assert str(seeded["fresh"].id) not in ids, "партнёр свежее 14 дней не должен попадать в список"
        assert str(seeded["stalled"].id) not in ids, "у партнёра были клиенты"
        assert str(seeded["alive"].id) not in ids
        assert str(seeded["blocked"].id) not in ids, "учитываются только активные"

        assert data["counts"]["no_clients"] == len(ids) == data["total"]

        item = next(i for i in data["items"] if i["id"] == str(seeded["never"].id))
        assert item["never_had_client"] is True
        assert item["clients_count"] == 0
        assert item["days_without_client"] >= 40
        assert item["last_client_at"] is None

    async def test_stalled_lists_long_pause_only(self, client: AsyncClient, admin_token):
        seeded = await _seed()

        data = await _list(client, admin_token, "stalled")
        ids = {item["id"] for item in data["items"]}

        assert str(seeded["stalled"].id) in ids
        assert str(seeded["alive"].id) not in ids, "клиент 3 дня назад — поток есть"
        assert str(seeded["never"].id) not in ids, "ни одного клиента — это «не рабочие»"

        item = next(i for i in data["items"] if i["id"] == str(seeded["stalled"].id))
        assert item["never_had_client"] is False
        assert item["clients_count"] == 1
        assert item["days_without_client"] >= 45
        assert item["last_client_at"] is not None

    async def test_counts_match_dashboard_card(self, client: AsyncClient, admin_token):
        await _seed()

        data = await _list(client, admin_token, "no_clients")
        dashboard = (await client.get(DASHBOARD, headers=auth(admin_token))).json()

        assert data["counts"]["no_clients"] == dashboard["risk_stats"]["partners_without_first_client"]

    async def test_oldest_pause_first(self, client: AsyncClient, admin_token):
        old = await _make_partner(email="old@test.com", company="Давний", created_days_ago=120)
        await _add_client(old.id, created_days_ago=60)
        recent = await _make_partner(email="recent@test.com", company="Недавний", created_days_ago=120)
        await _add_client(recent.id, created_days_ago=20)

        data = await _list(client, admin_token, "stalled")
        ids = [item["id"] for item in data["items"]]

        assert ids.index(str(old.id)) < ids.index(str(recent.id))

    async def test_counts_returned_for_both_modes(self, client: AsyncClient, admin_token):
        await _seed()

        no_clients = await _list(client, admin_token, "no_clients")
        stalled = await _list(client, admin_token, "stalled")

        assert no_clients["counts"] == stalled["counts"]
        assert no_clients["counts"]["no_clients"] == 1
        assert no_clients["counts"]["stalled"] == 1

    async def test_pagination(self, client: AsyncClient, admin_token):
        for index in range(3):
            await _make_partner(email=f"many{index}@test.com", company=f"Партнёр {index}", created_days_ago=40)

        first = await _list(client, admin_token, "no_clients", page_size=2)
        second = await _list(client, admin_token, "no_clients", page_size=2, page=2)

        assert len(first["items"]) == 2
        assert first["pages"] == 2
        assert len(second["items"]) == 1
        assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})

    async def test_invalid_mode(self, client: AsyncClient, admin_token):
        resp = await client.get(API, params={"mode": "unknown"}, headers=auth(admin_token))
        assert resp.status_code == 422

    async def test_partner_forbidden(self, client: AsyncClient, partner_token):
        resp = await client.get(API, headers=auth(partner_token))
        assert resp.status_code == 403

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get(API)
        assert resp.status_code in (401, 403)
