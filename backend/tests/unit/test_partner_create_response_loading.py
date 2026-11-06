"""Exercise real ORM expiration without an external PostgreSQL server.

SQLite runs through greenlet_spawn, with each SQL statement requiring an await.
This reproduces the async ORM's MissingGreenlet boundary on expired attributes.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.orm import Session
from sqlalchemy.util.concurrency import await_only, greenlet_spawn

from app.models.partner import Partner
from app.models.user import User
from app.schemas.partner import PartnerCreate
from app.services.partner_service import _partner_to_read, create_partner


@pytest.fixture
def setup_db():
    """These tests use an isolated in-memory database, not the global fixture."""


class AwaitingSQLiteSession:
    def __init__(self, session):
        self.sync = session

    def add(self, value):
        self.sync.add(value)

    async def execute(self, statement):
        return await greenlet_spawn(self.sync.execute, statement)

    async def flush(self):
        return await greenlet_spawn(self.sync.flush)

    async def refresh(self, value):
        return await greenlet_spawn(self.sync.refresh, value)

    @asynccontextmanager
    async def begin_nested(self):
        transaction = await greenlet_spawn(self.sync.begin_nested)
        try:
            yield
        except Exception:
            await greenlet_spawn(transaction.rollback)
            raise
        else:
            await greenlet_spawn(transaction.commit)


@pytest.fixture
def local_session():
    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    Partner.__table__.create(engine)

    @event.listens_for(engine, "before_cursor_execute")
    def require_await(*_args):
        await_only(asyncio.sleep(0))

    session = Session(engine, expire_on_commit=False)
    yield AwaitingSQLiteSession(session)
    event.remove(engine, "before_cursor_execute", require_await)
    session.close()
    engine.dispose()


@pytest.mark.parametrize("projection", ["pending", "not_installed", "failed"])
async def test_create_returns_loaded_response_after_projection(local_session, monkeypatch, projection):
    async def chat_rooms(*_args):
        return []

    async def schedule(session, partner):
        partner.bitrix_sync_status = "pending" if projection != "not_installed" else "not_scheduled"
        partner.bitrix_sync_error_code = "INSTALLATION_NOT_FOUND" if projection == "not_installed" else None
        if projection != "not_installed":
            await session.flush()
            assert "updated_at" in inspect(partner).expired_attributes
        if projection == "failed":
            raise RuntimeError("Projection failed after its database update")

    monkeypatch.setitem(sys.modules, "app.services.chat_service", SimpleNamespace(ensure_rooms_for_partner=chat_rooms))
    monkeypatch.setitem(
        sys.modules, "app.integrations.bitrix24.partners", SimpleNamespace(schedule_partner_creation=schedule)
    )
    monkeypatch.setattr("app.services.partner_service.hash_password", lambda _value: "test-hash")
    monkeypatch.setattr("app.services.partner_service.audit_log", lambda **_kwargs: None)

    result = await create_partner(
        local_session,
        PartnerCreate(
            email="regression@example.com",
            password="test-password",
            company_name="Regression partner",
            director_name="Test director",
            phone="+79990000000",
        ),
    )

    expected_status = {"pending": "pending", "not_installed": "not_scheduled", "failed": "failed"}
    assert result.bitrix_sync_status == expected_status[projection]
    assert result.email == "regression@example.com"
    assert result.updated_at is not None
    saved = await greenlet_spawn(local_session.sync.get, Partner, UUID(result.id))
    assert not inspect(saved).expired_attributes


async def test_unloaded_timestamp_reproduces_missing_greenlet(local_session):
    user = User(email="expired@example.com", hashed_password="test-hash", role="partner", is_active=True)
    local_session.add(user)
    await local_session.flush()
    partner = Partner(
        user_id=user.id, company_name="Test", director_name="Test", inn="", phone="+79990000000"
    )
    local_session.add(partner)
    await local_session.flush()
    partner.bitrix_sync_status = "pending"
    await local_session.flush()
    assert "updated_at" in inspect(partner).expired_attributes

    with pytest.raises(MissingGreenlet):
        _partner_to_read(partner, email=user.email)

    await local_session.refresh(partner)
    assert _partner_to_read(partner, email=user.email).updated_at is not None
    assert _partner_to_read(partner, email="partner-43@no-login.invalid").email is None
    assert _partner_to_read(partner, email="").email is None
    assert _partner_to_read(partner, email=user.email).email == user.email
