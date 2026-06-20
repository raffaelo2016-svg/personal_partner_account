from datetime import datetime

from pydantic import BaseModel


class FileUploadRead(BaseModel):
    file_id: str
    url: str
    filename: str
    size: int
    mime_type: str
    document_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FilePresignedURL(BaseModel):
    file_id: str
    url: str
    filename: str
