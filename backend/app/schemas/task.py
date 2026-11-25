from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator


class TaskDeadline(BaseModel):
    due_date: date | None = None
    due_at: AwareDatetime | None = None

    @field_validator("due_at")
    @classmethod
    def deadline_in_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None


class TaskCreate(TaskDeadline):
    partner_id: str | None = None
    client_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    assigned_to: Literal["partner", "uritech", "admin"] = "partner"

    @model_validator(mode="after")
    def require_owner(self) -> "TaskCreate":
        if not self.client_id and not self.partner_id:
            raise ValueError("Укажите клиента или партнёра")
        return self


class TaskUpdate(TaskDeadline):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: Literal["pending", "in_progress", "completed"] | None = None
    priority: Literal["low", "medium", "high"] | None = None
    assigned_to: Literal["partner", "uritech", "admin"] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "TaskUpdate":
        for name in ("title", "status", "priority", "assigned_to"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TaskClientBrief(BaseModel):
    id: str
    full_name: str
    case_number: str | None = None
    status: str
    phone: str | None = None
    arbitrage_court: str | None = None


class TaskFileRead(BaseModel):
    id: str
    task_id: str
    client_id: str | None = None
    original_name: str
    size: int
    mime_type: str
    created_at: datetime
    uploader_id: str
    uploader_name: str
    can_delete: bool
    download_url: str
    task_title: str | None = None


class TaskMessageRead(BaseModel):
    id: str
    task_id: str
    author_id: str | None = None
    author_name: str
    author_role: str
    text: str
    created_at: datetime
    is_mine: bool


class TaskEventRead(BaseModel):
    id: str
    type: str
    actor_name: str | None = None
    payload: dict[str, Any] = {}
    created_at: datetime


class TaskPermissions(BaseModel):
    is_admin: bool
    can_edit: bool
    can_upload: bool
    can_request_review: bool
    can_approve: bool
    can_return: bool
    can_delete_task: bool


class TaskRead(BaseModel):
    id: str
    partner_id: str | None = None
    partner_name: str | None = None
    client_id: str | None = None
    title: str
    description: str | None = None
    status: str
    priority: str
    assigned_to: str
    created_by: str
    due_date: date | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    review_requested_at: datetime | None = None
    review_requested_by: str | None = None
    files_count: int = 0
    messages_count: int = 0
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime
    client_name: str | None = None
    bitrix_sync_status: str = "not_scheduled"
    bitrix_sync_error_code: str | None = None
    bitrix_task_id: str | None = None
    bitrix_imported: bool = False
    bitrix_published: bool = True
    bitrix_sync_requested_at: datetime | None = None
    bitrix_synced_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskDetailRead(TaskRead):
    client: TaskClientBrief | None = None
    files: list[TaskFileRead] = []
    messages: list[TaskMessageRead] = []
    events: list[TaskEventRead] = []
    permissions: TaskPermissions


class TaskMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TaskReviewRequest(BaseModel):
    action: Literal["request", "approve", "return"]


class TaskStats(BaseModel):
    total: int
    pending: int
    in_progress: int
    review: int = 0
    completed: int
    overdue: int
    completion_percent: float
