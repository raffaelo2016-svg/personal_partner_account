from datetime import datetime

from pydantic import BaseModel, Field


class AgentProfile(BaseModel):
    id: str
    code: str
    full_name: str
    phone: str
    company_name: str | None
    status: str
    requisites_status: str
    requisites_recipient_type: str
    referral_link: str


class AgentStats(BaseModel):
    partners: int
    clients: int
    accrued: int
    reserved: int
    paid: int
    available: int


class AgentMe(BaseModel):
    profile: AgentProfile
    stats: AgentStats


class AgentPartner(BaseModel):
    id: str
    name: str
    status: str
    linked_at: datetime | None
    clients: int
    accrued: int


class AgentAccrualRead(BaseModel):
    id: str
    client_ref: str
    partner_name: str
    created_at: datetime
    amount: int
    rate: int
    status: str
    reason: str


class PayoutRead(BaseModel):
    id: str
    amount: int
    status: str
    period: str
    created_at: datetime
    paid_at: datetime | None
    comment: str | None


class RequisitesUpdate(BaseModel):
    recipient_type: str = Field(pattern=r"^(individual|ip|company)$")
    data: dict


class AgentRegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(default="", max_length=30)
    company_name: str | None = Field(default=None, max_length=255)


class AdminAgentRead(BaseModel):
    id: str
    email: str
    code: str
    full_name: str
    company_name: str | None
    status: str
    created_at: datetime
    requisites_status: str
    stats: AgentStats


class AdminAgentDetail(BaseModel):
    agent: AdminAgentRead
    partners: list[AgentPartner]
    accruals: list[AgentAccrualRead]
    payouts: list[PayoutRead]


class AgentStatusUpdate(BaseModel):
    is_active: bool
    reason: str | None = Field(default=None, max_length=500)


class RequisitesReviewRequest(BaseModel):
    status: str = Field(pattern=r"^(accepted|needs_fix)$")
    comment: str | None = Field(default=None, max_length=500)


class PartnerBindRequest(BaseModel):
    agent_id: str | None = None
    reason: str = Field(min_length=3, max_length=500)
    force: bool = False


class PayoutStatusRequest(BaseModel):
    status: str = Field(pattern=r"^(submitted|checking|scheduled|paid|needs_fix|cancelled)$")
    comment: str | None = Field(default=None, max_length=500)
