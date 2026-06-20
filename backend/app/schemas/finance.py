from datetime import date, datetime

from pydantic import BaseModel


class CourtFeeRead(BaseModel):
    id: str
    client_id: str
    partner_id: str
    amount: int
    status: str
    due_date: date
    paid_at: datetime | None = None
    created_at: datetime
    client_name: str | None = None
    client_status: str | None = None
    court_procedure_date: date | None = None

    model_config = {"from_attributes": True}


class CourtFeeSummary(BaseModel):
    fee_per_client: int
    total_debt: int
    current_debt: int
    overdue_debt: int
    paid_this_month: int
    unpaid_count: int
    current_count: int
    overdue_count: int
    total_clients: int
    payment_term_days: int


class DebtBanner(BaseModel):
    total_debt: int
    overdue: int
    has_debt: bool
    days_until_next_payment: int | None = None


class PayRequest(BaseModel):
    court_fee_id: str
    payment_method: str = "card"


class TransactionRead(BaseModel):
    id: str
    partner_id: str
    court_fee_id: str | None = None
    amount: int
    status: str
    payment_method: str | None = None
    external_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminTransactionRead(BaseModel):
    id: str
    partner_id: str
    partner_name: str
    client_name: str | None = None
    amount: int
    status: str
    payment_method: str | None = None
    external_id: str | None = None
    created_at: datetime
