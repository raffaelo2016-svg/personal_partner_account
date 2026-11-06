import uuid
from datetime import datetime

from pydantic import BaseModel


class SystemSettingRead(BaseModel):
    key: str
    value: str
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SystemSettingUpdate(BaseModel):
    settings: dict[str, str]


class NotificationPreferenceRead(BaseModel):
    user_id: uuid.UUID
    email_notifications: bool
    new_partner_notifications: bool
    critical_events: bool
    telegram_notifications: bool

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    email_notifications: bool | None = None
    new_partner_notifications: bool | None = None
    critical_events: bool | None = None
    telegram_notifications: bool | None = None


class TelegramConnectionRead(BaseModel):
    available: bool
    connected: bool
    username: str | None = None
    notifications_enabled: bool


class TelegramConnectRead(BaseModel):
    url: str
    expires_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class LoginHistoryRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    logged_at: datetime

    model_config = {"from_attributes": True}
