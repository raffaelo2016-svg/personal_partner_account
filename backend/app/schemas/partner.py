from datetime import datetime
from typing import Self

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import PartnerStatus
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
    court_fee_per_client: int = 1_500_000
    payment_term_days: int = 10

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
    court_fee_per_client: int | None = None
    payment_term_days: int | None = None
    status: PartnerStatus | None = None


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
    court_fee_per_client: int
    payment_term_days: int
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


class PartnerBitrixCollabBinding(BaseModel):
    collab_id: str = Field(min_length=1, max_length=100)
    chat_id: str = Field(min_length=1, max_length=100)
    root_folder_id: str = Field(min_length=1, max_length=100)
