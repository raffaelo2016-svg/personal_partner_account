import uuid
from datetime import datetime

from pydantic import BaseModel


class TrainingVideoRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    duration: int | None = None
    video_url: str
    thumbnail_url: str | None = None
    order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FAQRead(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InstructionRead(BaseModel):
    id: uuid.UUID
    title: str
    steps: dict
    order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportantNoteRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    icon: str | None = None
    order: int
    created_at: datetime

    model_config = {"from_attributes": True}
