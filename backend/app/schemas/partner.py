from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import PartnerStatus
from app.validation.regions import normalize_region
from app.validation.ru_requisites import normalize_and_validate_partner_inn_kpp


class PartnerCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    partner_type: str = Field(default="individual", pattern=r"^(individual|legal|entrepreneur)$")
    company_name: str = Field(min_length=1, max_length=255)
    director_name: str = Field(min_length=1, max_length=255)
    inn: str = Field(default="", max_length=12)
    phone: str = Field(min_length=5, max_length=30)
    short_name: str | None = None
    full_legal_name: str | None = None
    legal_address: str | None = None
    postal_address: str | None = None
    kpp: str | None = None
    region: str | None = None
    court_fee_per_client: int = 1_500_000
    payment_term_days: int = 10
    free_client_limit: int = Field(default=0, ge=0, le=10_000)
    promotion_start_date: date | None = None

    @field_validator("region")
    @classmethod
    def _validate_region(cls, value: str | None) -> str | None:
        return normalize_region(value)

    @model_validator(mode="after")
    def _normalize_inn_kpp(self) -> Self:
        inn, kpp = normalize_and_validate_partner_inn_kpp(self.partner_type, self.inn, self.kpp)
        self.inn = inn
        self.kpp = kpp
        return self


class PartnerUpdate(BaseModel):
    partner_type: str | None = None
    company_name: str | None = None
    director_name: str | None = None
    inn: str | None = None
    phone: str | None = None
    short_name: str | None = None
    full_legal_name: str | None = None
    legal_address: str | None = None
    postal_address: str | None = None
    kpp: str | None = None
    region: str | None = None
    court_fee_per_client: int | None = None
    payment_term_days: int | None = None
    free_client_limit: int | None = Field(default=None, ge=0, le=10_000)
    promotion_start_date: date | None = None
    status: PartnerStatus | None = None

    @field_validator("region")
    @classmethod
    def _validate_region(cls, value: str | None) -> str | None:
        return normalize_region(value)


class PartnerRead(BaseModel):
    id: str
    user_id: str
    email: str | None = None
    partner_type: str
    company_name: str
    director_name: str
    inn: str
    phone: str
    short_name: str | None = None
    full_legal_name: str | None = None
    legal_address: str | None = None
    postal_address: str | None = None
    kpp: str | None = None
    region: str | None = None
    timezone: str | None = None
    court_fee_per_client: int
    payment_term_days: int
    free_client_limit: int = 0
    promotion_start_date: date | None = None
    promotion_end_date: date | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    bitrix_sync_status: str = "not_scheduled"
    bitrix_sync_error_code: str | None = None
    bitrix_partner_item_id: str | None = None
    bitrix_collab_status: str = "not_linked"
    bitrix_collab_id: str | None = None
    bitrix_chat_id: str | None = None
    bitrix_root_folder_id: str | None = None
    bitrix_sync_requested_at: datetime | None = None
    bitrix_synced_at: datetime | None = None
    clients_count: int = 0
    active_cases_count: int = 0
    before_court_count: int = 0
    in_court_count: int = 0
    completed_count: int = 0
    finance_total_cost: int = 0
    finance_current_debt: int = 0
    finance_overdue_debt: int = 0
    finance_paid: int = 0

    model_config = {"from_attributes": True}


class PartnerStats(BaseModel):
    total_partners: int
    active_partners: int
    total_clients: int
    pending_partners: int


class PartnerClientPauseRead(BaseModel):
    """Партнёр без клиентского потока: «не рабочий» или «затихший»."""

    id: str
    company_name: str
    director_name: str
    email: str | None = None
    phone: str
    status: str
    created_at: datetime
    last_client_at: datetime | None = None
    clients_count: int = 0
    days_without_client: int
    never_had_client: bool


class PartnerClientPauseCounts(BaseModel):
    no_clients: int = 0
    stalled: int = 0


class PartnerClientPauseResponse(BaseModel):
    items: list[PartnerClientPauseRead]
    total: int
    page: int
    pages: int
    page_size: int
    mode: str
    counts: PartnerClientPauseCounts


class PartnerBitrixCollabBinding(BaseModel):
    collab_id: str | None = Field(default=None, min_length=1, max_length=100)
    chat_id: str | None = Field(default=None, min_length=1, max_length=100)
    root_folder_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _require_identifier(self) -> Self:
        if not any((self.collab_id, self.chat_id, self.root_folder_id)):
            raise ValueError("Укажите хотя бы один идентификатор Битрикс24")
        return self
