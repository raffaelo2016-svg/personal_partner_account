from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    client_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: str = "medium"
    assigned_to: str = "partner"
    due_date: date


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: Literal["pending", "in_progress", "completed"] | None = None
    priority: str | None = None
    assigned_to: str | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    id: str
    client_id: str
    title: str
    description: str | None = None
    status: str
    priority: str
    assigned_to: str
    created_by: str
    due_date: date
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    client_name: str | None = None
    bitrix_sync_status: str = "not_scheduled"
    bitrix_sync_error_code: str | None = None
    bitrix_task_id: str | None = None
    bitrix_sync_requested_at: datetime | None = None
    bitrix_synced_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskStats(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    overdue: int
    completion_percent: float
