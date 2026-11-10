from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SetupStatus(BaseModel):
    needs_setup: bool


class BootstrapRequest(BaseModel):
    key: str = Field(min_length=8, max_length=256)
    email: str = Field(min_length=5, max_length=255)
    login: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="admin", pattern=r"^(admin|super_admin|agent)$")
    ttl_hours: int = Field(default=72)


class InviteRead(BaseModel):
    id: str
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    created_by_label: str | None = None
    invite_url: str | None = None


class InviteInfo(BaseModel):
    email: str
    role: str
    status: str
    expires_at: datetime
    inviter_label: str | None = None


class RegisterByInviteRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    login: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=30)


class AdminRead(BaseModel):
    id: str
    email: str
    login: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    is_legacy_shared: bool


class AdminUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|super_admin)$")
    is_active: bool | None = None


class AuditEntry(BaseModel):
    id: str
    created_at: datetime
    actor_label: str | None
    action: str
    target_label: str | None
    result: str
    ip_address: str | None
    user_agent: str | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


class MessageResponse(BaseModel):
    message: str
