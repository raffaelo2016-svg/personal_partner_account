"""Task ownership and deadlines against a local SQL database, without external services."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Uuid, create_engine, event, inspect, literal, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import visitors

from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequest, Forbidden
from app.database import get_db
from app.integrations.bitrix24.client import Bitrix24Error
from app.main import app
from app.models import Base
from app.models.client import Client
from app.models.partner import Partner
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import (
    _effective_status,
    create_task,
    delete_task,
    get_task_stats,
    get_urgent_tasks,
    list_tasks,
    retry_task_bitrix_sync,
    update_task,
)


@pytest.fixture(autouse=True)
def setup_db():
    """Override the repository's PostgreSQL fixture for this self-contained suite."""
    yield


class _AsyncSessionAdapter:
    """Run the production SQL statements on SQLite through awaitable session methods."""

    def __init__(self, session):
        self.sync = session

    def add(self, instance):
        self.sync.add(instance)

    async def get(self, model, ident, **kwargs):
        if isinstance(ident, str):
            ident = UUID(ident)
        return self.sync.get(model, ident, **kwargs)

    async def execute(self, statement):
        def coerce_uuid_bind(element):
            if isinstance(element.type, Uuid):
                if isinstance(element.value, str):
                    element.value = UUID(element.value)
                if isinstance(element.value, list) and any(isinstance(value, str) for value in element.value):
                    element.value = [UUID(value) if isinstance(value, str) else value for value in element.value]

        statement = visitors.cloned_traverse(statement, {}, {"bindparam": coerce_uuid_bind})
        return self.sync.execute(statement)

    async def flush(self):
        self.sync.flush()

    async def refresh(self, instance, attribute_names=None):
        self.sync.refresh(instance, attribute_names)

    async def delete(self, instance):
        self.sync.delete(instance)

    async def commit(self):
        self.sync.commit()


@pytest.fixture
async def task_db():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        # SQLite's UUID binder requires UUID instances; PostgreSQL accepts the
        # normal string API IDs. Adapt values locally without mutating shared
        # model metadata or invalidating SQLAlchemy's mapper compilation cache.
        @event.listens_for(session, "before_flush")
        def coerce_uuid_attributes(sync_session, flush_context, instances):
            for instance in sync_session.new | sync_session.dirty:
                for attribute in inspect(instance).mapper.column_attrs:
                    if isinstance(attribute.columns[0].type, Uuid):
                        value = getattr(instance, attribute.key)
                        if isinstance(value, str):
                            setattr(instance, attribute.key, UUID(value))

        adapter = _AsyncSessionAdapter(session)
        with (
            patch("app.integrations.bitrix24.tasks.schedule_task_creation", new_callable=AsyncMock),
            patch("app.services.task_service.audit_log"),
        ):
            yield adapter
    engine.dispose()


@pytest.fixture
async def people(task_db):
    users = [
        User(email=f"tasks-{n}@example.test", hashed_password="unused", role="admin" if n == 0 else "partner")
        for n in range(3)
    ]
    task_db.sync.add_all(users)
    await task_db.flush()
    partners = [
        Partner(user_id=users[n].id, company_name=f"Partner {n}", director_name="Director", inn="123", phone="1")
        for n in (1, 2)
    ]
    task_db.sync.add_all(partners)
    await task_db.flush()
    clients = [Client(partner_id=p.id, type="before_court", full_name=f"Client {n}") for n, p in enumerate(partners)]
    task_db.sync.add_all(clients)
    await task_db.flush()
    return users[0], partners[0], partners[1], clients[0], clients[1]


async def _received(task_db, people, **values):
    admin, partner, _, _, _ = people
    return await create_task(
        task_db,
        TaskCreate(partner_id=str(partner.id), title="Partner task", **values),
        str(admin.id),
    )


async def test_admin_can_create_general_partner_task_without_deadline(task_db, people):
    created = await _received(task_db, people)
    assert created.partner_id == str(people[1].id)
    assert created.partner_name == "Partner 1"
    assert created.client_id is None
    assert created.due_date is None and created.due_at is None
    assert created.status == "pending"


async def test_client_task_gets_explicit_partner_and_rejects_conflicting_pair(task_db, people):
    admin, partner, other, client, _ = people
    created = await create_task(task_db, TaskCreate(client_id=str(client.id), title="Client task"), str(admin.id))
    assert created.partner_id == str(partner.id)
    with pytest.raises(BadRequest):
        await create_task(
            task_db,
            TaskCreate(client_id=str(client.id), partner_id=str(other.id), title="Wrong pair"),
            str(admin.id),
        )


async def test_partner_cannot_self_assign_or_address_another_partner(task_db, people):
    admin, partner, other, _, _ = people
    with pytest.raises(Forbidden):
        await create_task(
            task_db, TaskCreate(partner_id=str(partner.id), title="Self assigned"),
            str(admin.id), partner_id=str(partner.id),
        )
    with pytest.raises(Forbidden):
        await create_task(
            task_db, TaskCreate(partner_id=str(other.id), title="Other", assigned_to="uritech"),
            str(admin.id), partner_id=str(partner.id),
        )
    outgoing = await create_task(
        task_db, TaskCreate(title="Request", assigned_to="uritech"),
        str(admin.id), partner_id=str(partner.id),
    )
    assert outgoing.assigned_to == "uritech"
    assert outgoing.partner_id == str(partner.id)
    with pytest.raises(BadRequest):
        await create_task(task_db, TaskCreate(title="No recipient"), str(admin.id))


async def test_revoked_publication_hides_task_and_removes_partner_control(task_db, people):
    created = await _received(task_db, people)
    task = await task_db.get(Task, created.id)
    task.bitrix_imported = True
    task.bitrix_published = False
    await task_db.flush()
    owner_id = str(people[1].id)
    items, count = await list_tasks(task_db, partner_id=owner_id)
    assert items == [] and count == 0
    assert (await get_task_stats(task_db, partner_id=owner_id)).total == 0
    assert await get_urgent_tasks(task_db, partner_id=owner_id) == []
    with pytest.raises(Forbidden):
        await update_task(task_db, created.id, TaskUpdate(status="completed"), partner_id=owner_id)
    with pytest.raises(Forbidden):
        await retry_task_bitrix_sync(task_db, created.id, partner_id=owner_id)
    with pytest.raises(Forbidden):
        await delete_task(task_db, created.id, partner_id=owner_id)
    admin_items, admin_count = await list_tasks(task_db)
    assert admin_count == 1 and admin_items[0].bitrix_published is False


async def test_general_and_legacy_tasks_are_isolated_with_explicit_owner_priority(task_db, people):
    admin, partner, other, client, _ = people
    own = await _received(task_db, people)
    legacy = Task(client_id=client.id, title="Legacy", assigned_to="partner", created_by=admin.id)
    conflict = Task(
        client_id=client.id, partner_id=other.id, title="Other owner wins", assigned_to="partner", created_by=admin.id,
    )
    task_db.sync.add_all([legacy, conflict])
    await task_db.flush()
    items, count = await list_tasks(task_db, partner_id=str(partner.id))
    assert count == 2
    assert {item.id for item in items} == {own.id, str(legacy.id)}
    assert all(item.partner_id == str(partner.id) for item in items)
    stats = await get_task_stats(task_db, partner_id=str(partner.id))
    assert stats.total == 2
    urgent = await get_urgent_tasks(task_db, partner_id=str(partner.id))
    assert {item.id for item in urgent} == {own.id, str(legacy.id)}
    with pytest.raises(Forbidden):
        await update_task(task_db, own.id, TaskUpdate(status="completed"), partner_id=str(other.id))
    with pytest.raises(Forbidden):
        await delete_task(task_db, own.id, partner_id=str(other.id))


@pytest.mark.parametrize("changes", [{"title": "Changed"}, {"due_at": "2026-12-01T12:00:00+03:00"},
                                     {"assigned_to": "uritech"}, {"description": None}, {"priority": "high"}])
async def test_received_partner_tasks_only_allow_status_updates(task_db, people, changes):
    created = await _received(task_db, people)
    with pytest.raises(Forbidden):
        await update_task(task_db, created.id, TaskUpdate(**changes), partner_id=str(people[1].id))


async def test_received_partner_can_complete_and_sync_status_but_not_delete_or_retry(task_db, people):
    created = await _received(task_db, people)
    task = await task_db.get(Task, created.id)
    task.bitrix_task_id = "77"
    await task_db.flush()
    with patch("app.integrations.bitrix24.tasks.sync_task_status", new_callable=AsyncMock) as sync:
        updated = await update_task(
            task_db, created.id, TaskUpdate(status="completed"), partner_id=str(people[1].id),
        )
        sync.assert_awaited_once()
    assert updated.status == "completed" and updated.completed_at is not None
    with pytest.raises(Forbidden):
        await delete_task(task_db, created.id, partner_id=str(people[1].id))
    with pytest.raises(Forbidden):
        await retry_task_bitrix_sync(task_db, created.id, partner_id=str(people[1].id))


async def test_precise_deadline_normalization_move_and_removal(task_db, people):
    created = await _received(task_db, people, due_at="2030-12-31T23:30:00Z", due_date="2030-01-01")
    assert created.due_date == date(2031, 1, 1)
    updated = await update_task(task_db, created.id, TaskUpdate(due_at="2031-01-03T12:30:00+03:00"))
    assert updated.due_at == datetime(2031, 1, 3, 9, 30, tzinfo=UTC)
    assert updated.due_date == date(2031, 1, 3)
    cleared = await update_task(task_db, created.id, TaskUpdate(due_at=None))
    assert cleared.due_at is None and cleared.due_date is None
    date_only = await update_task(task_db, created.id, TaskUpdate(due_date=date(2031, 2, 1)))
    assert date_only.due_date == date(2031, 2, 1) and date_only.due_at is None
    reset = await update_task(task_db, created.id, TaskUpdate(due_at="2031-03-01T12:00:00Z"))
    assert reset.due_at is not None
    date_only_again = await update_task(task_db, created.id, TaskUpdate(due_date=date(2031, 4, 1)))
    assert date_only_again.due_at is None


async def test_linked_admin_edits_sync_normalized_deadline_and_fail_without_local_write(task_db, people):
    created = await _received(task_db, people)
    task = await task_db.get(Task, created.id)
    task.bitrix_task_id = "77"
    task.bitrix_imported = True
    await task_db.flush()
    with patch("app.integrations.bitrix24.tasks.sync_task_fields", new_callable=AsyncMock) as sync:
        updated = await update_task(task_db, created.id, TaskUpdate(due_at="2031-12-31T23:00:00Z"))
        sent = sync.await_args.args[2]
        assert sent["due_date"] == date(2032, 1, 1)
        assert isinstance(sent["due_at"], datetime)
        assert updated.due_date == date(2032, 1, 1)
    with (
        patch(
            "app.integrations.bitrix24.tasks.sync_task_fields",
            new=AsyncMock(side_effect=Bitrix24Error("REMOTE_FAILED", "Remote unavailable")),
        ),
        pytest.raises(BadRequest),
    ):
        await update_task(task_db, created.id, TaskUpdate(title="Rejected"))
    assert task.title == "Partner task"
    with pytest.raises(BadRequest):
        await update_task(task_db, created.id, TaskUpdate(assigned_to="uritech"))


async def test_deleting_partner_removes_general_tasks_without_clients(task_db, people):
    from app.services.partner_service import delete_partner

    admin, partner, other, client, _ = people
    await task_db.delete(client)
    await task_db.flush()
    own = await _received(task_db, people)
    preserved = await create_task(
        task_db, TaskCreate(partner_id=str(other.id), title="Other task"), str(admin.id),
    )
    with patch("app.services.partner_service.audit_log"):
        await delete_partner(task_db, str(partner.id))
    ids = set(task_db.sync.scalars(select(Task.id)))
    assert UUID(own.id) not in ids
    assert UUID(preserved.id) in ids


async def test_overdue_stats_and_filters_use_exact_time_and_preserve_lifecycle(task_db, people):
    now = datetime.now(UTC)
    expired = await _received(task_db, people, due_at=now - timedelta(minutes=1))
    future = await _received(task_db, people, due_at=now + timedelta(hours=1))
    no_deadline = await _received(task_db, people)
    task = await task_db.get(Task, expired.id)
    task.status = "in_progress"
    await task_db.flush()
    items, count = await list_tasks(task_db, partner_id=str(people[1].id), status="overdue")
    assert count == 1 and items[0].id == expired.id
    stats = await get_task_stats(task_db, partner_id=str(people[1].id))
    assert stats.total == 3 and stats.overdue == 1 and stats.pending == 2
    assert task.status == "in_progress"
    extended = await update_task(task_db, expired.id, TaskUpdate(due_at=now + timedelta(days=1)))
    assert extended.status == "in_progress"
    stats = await get_task_stats(task_db, partner_id=str(people[1].id))
    assert stats.overdue == 0 and stats.in_progress == 1
    pending, _ = await list_tasks(task_db, partner_id=str(people[1].id), status="pending")
    assert {item.id for item in pending} == {future.id, no_deadline.id}


def test_date_only_deadline_expires_at_moscow_midnight():
    task = Task(status="pending", due_date=date(2026, 10, 15))
    assert _effective_status(task, datetime(2026, 10, 15, 20, 59, 59, tzinfo=UTC)) == "pending"
    assert _effective_status(task, datetime(2026, 10, 15, 21, 0, 0, tzinfo=UTC)) == "overdue"
    task.due_at = datetime(2026, 10, 16, 12, tzinfo=UTC)
    assert _effective_status(task, datetime(2026, 10, 15, 21, tzinfo=UTC)) == "pending"
    task.status = "completed"
    assert _effective_status(task, datetime(2026, 10, 17, tzinfo=UTC)) == "completed"


async def test_dashboard_includes_general_tasks_and_nullable_deadlines(task_db, people):
    from app.api.dashboard import partner_dashboard

    partner = people[1]
    pending = await _received(task_db, people, priority="high")
    completed = await _received(task_db, people, priority="high")
    await update_task(task_db, completed.id, TaskUpdate(status="completed"))
    execute = task_db.execute

    async def dashboard_execute(statement):
        # The pre-existing client activity query uses a PostgreSQL interval;
        # task queries below run unchanged against the local SQL database.
        if "interval '7 days'" in str(statement):
            return task_db.sync.execute(select(literal(0)))
        return await execute(statement)

    with (
        patch.object(task_db, "execute", dashboard_execute),
        patch("app.api.dashboard._get_partner_id_for_user", new=AsyncMock(return_value=str(partner.id))),
    ):
        result = await partner_dashboard(db=task_db, current_user=partner.user)
    assert result["task_completion"] == {"percent": 50, "total": 2, "completed": 1}
    assert len(result["urgent_tasks"]) == 1
    assert result["urgent_tasks"][0]["id"] == pending.id
    assert result["urgent_tasks"][0]["due_at"] is None
    assert result["urgent_tasks"][0]["due_date"] is None
    assert result["urgent_tasks"][0]["client_id"] is None


async def test_api_general_task_admin_creation_and_partner_filter_protection(task_db, people):
    admin, partner, other, _, _ = people
    previous = dict(app.dependency_overrides)

    async def db_override():
        yield task_db

    async def admin_override():
        return admin

    async def partner_override():
        return partner.user

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = admin_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
            response = await api.post("/api/v1/tasks", json={"partner_id": str(partner.id), "title": "General"})
            assert response.status_code == 201, response.text
            task_id = response.json()["id"]
            app.dependency_overrides[get_current_user] = partner_override
            response = await api.get("/api/v1/tasks", params={"partner_id": str(other.id)})
            assert response.status_code == 403
            response = await api.get("/api/v1/tasks")
            assert response.status_code == 200 and response.json()["total"] == 1
            response = await api.put(f"/api/v1/tasks/{task_id}", json={"due_date": "2031-01-01"})
            assert response.status_code == 403
            response = await api.put(f"/api/v1/tasks/{task_id}", json={"status": "completed"})
            assert response.status_code == 200 and response.json()["status"] == "completed"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
