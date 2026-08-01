from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ClientStatus, ClientType


class ClientCreate(BaseModel):
    type: ClientType
    full_name: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    passport_series: str | None = Field(None, max_length=4)
    passport_number: str | None = Field(None, max_length=6)
    passport_issue_date: date | None = None
    passport_issued_by: str | None = None
    registration_address: str | None = None
    inn: str | None = Field(None, max_length=12)
    snils: str | None = Field(None, max_length=14)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    region: str | None = Field(None, max_length=100)
    arbitrage_court: str | None = Field(None, max_length=255)
    case_number: str | None = Field(None, max_length=50)


class ClientUpdate(BaseModel):
    type: ClientType | None = None
    status: ClientStatus | None = None
    full_name: str | None = Field(None, max_length=255)
    date_of_birth: date | None = None
    passport_series: str | None = Field(None, max_length=4)
    passport_number: str | None = Field(None, max_length=6)
    passport_issue_date: date | None = None
    passport_issued_by: str | None = None
    registration_address: str | None = None
    inn: str | None = Field(None, max_length=12)
    snils: str | None = Field(None, max_length=14)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    region: str | None = Field(None, max_length=100)
    arbitrage_court: str | None = Field(None, max_length=255)
    case_number: str | None = Field(None, max_length=50)
    court_procedure_date: date | None = None


class ClientRead(BaseModel):
    id: str
    partner_id: str
    partner_name: str | None = None
    type: str
    status: str
    full_name: str
    date_of_birth: date | None = None
    passport_series: str | None = None
    passport_number: str | None = None
    passport_issue_date: date | None = None
    passport_issued_by: str | None = None
    registration_address: str | None = None
    inn: str | None = None
    snils: str | None = None
    phone: str | None = None
    email: str | None = None
    region: str | None = None
    arbitrage_court: str | None = None
    case_number: str | None = None
    court_procedure_date: date | None = None
    court_fee_per_client: int | None = None
    bitrix_sync_status: str = "not_scheduled"
    bitrix_sync_error_code: str | None = None
    bitrix_contact_id: str | None = None
    bitrix_deal_id: str | None = None
    bitrix_sync_requested_at: datetime | None = None
    bitrix_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientStats(BaseModel):
    total: int
    before_court: int
    in_court: int
    completed: int
    new_this_week: int
