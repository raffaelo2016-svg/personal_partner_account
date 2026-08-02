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
    bitrix_sync_status: str = "not_scheduled"
    bitrix_sync_error_code: str | None = None
    bitrix_disk_file_id: str | None = None

    model_config = {"from_attributes": True}


class FilePresignedURL(BaseModel):
    file_id: str
    url: str
    filename: str
