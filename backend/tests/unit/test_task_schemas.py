"""Unit-тесты: Task schemas + enums."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskStats, TaskUpdate


class TestTaskCreate:
    def test_valid_minimal(self):
        t = TaskCreate(client_id="abc", title="X", due_date="2026-06-01")
        assert t.priority == "medium"
        assert t.assigned_to == "partner"

    def test_recipient_can_be_inferred_from_authenticated_partner(self):
        task = TaskCreate(title="X", assigned_to="uritech", due_date="2026-06-01")
        assert task.client_id is None and task.partner_id is None

    def test_missing_title(self):
        with pytest.raises(ValidationError):
            TaskCreate(client_id="a", due_date="2026-06-01")  # type: ignore

    def test_empty_title(self):
        with pytest.raises(ValidationError):
            TaskCreate(client_id="a", title="", due_date="2026-06-01")

    def test_title_max(self):
        t = TaskCreate(client_id="a", title="Б" * 255, due_date="2026-06-01")
        assert len(t.title) == 255

    def test_title_over_max(self):
        with pytest.raises(ValidationError):
            TaskCreate(client_id="a", title="Б" * 256, due_date="2026-06-01")

    def test_missing_due_date(self):
        t = TaskCreate(client_id="a", title="X")
        assert t.due_date is None and t.due_at is None

    def test_general_partner_task(self):
        t = TaskCreate(partner_id="partner", title="Подписать договор")
        assert t.client_id is None

    def test_precise_deadline_requires_timezone(self):
        with pytest.raises(ValidationError):
            TaskCreate(client_id="a", title="X", due_at="2026-12-01T12:00:00")

    def test_invalid_due_date(self):
        with pytest.raises(ValidationError):
            TaskCreate(client_id="a", title="X", due_date="not-a-date")

    def test_description_optional(self):
        t = TaskCreate(client_id="a", title="X", due_date="2026-06-01")
        assert t.description is None

    def test_with_description(self):
        t = TaskCreate(client_id="a", title="X", due_date="2026-06-01", description="Подробности")
        assert t.description == "Подробности"


class TestTaskUpdate:
    def test_empty(self):
        u = TaskUpdate()
        assert u.title is None

    def test_exclude_unset(self):
        u = TaskUpdate(title="New")
        assert u.model_dump(exclude_unset=True) == {"title": "New"}

    def test_update_status(self):
        u = TaskUpdate(status="completed")
        assert u.status == "completed"

    def test_update_due_date(self):
        u = TaskUpdate(due_date="2026-12-31")
        assert u.due_date == date(2026, 12, 31)


class TestTaskEnums:
    def test_task_status_values(self):
        assert set(TaskStatus) == {"pending", "in_progress", "completed", "overdue"}

    def test_task_priority_values(self):
        assert set(TaskPriority) == {"low", "medium", "high"}

    def test_task_status_count(self):
        assert len(TaskStatus) == 4

    def test_task_priority_count(self):
        assert len(TaskPriority) == 3


class TestTaskStats:
    def test_valid(self):
        s = TaskStats(total=10, pending=3, in_progress=2, completed=4, overdue=1, completion_percent=40.0)
        assert s.completion_percent == 40.0

    def test_zero_stats(self):
        s = TaskStats(total=0, pending=0, in_progress=0, completed=0, overdue=0, completion_percent=0.0)
        assert s.total == 0
