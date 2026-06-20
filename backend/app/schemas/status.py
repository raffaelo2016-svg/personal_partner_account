from datetime import datetime

from pydantic import BaseModel


class ChangeStatusRequest(BaseModel):
    status: str
    comment: str | None = None


class StatusLogRead(BaseModel):
    id: int
    client_id: str
    from_status: str
    to_status: str
    changed_by: str
    comment: str | None = None
    changed_at: datetime

    model_config = {"from_attributes": True}
