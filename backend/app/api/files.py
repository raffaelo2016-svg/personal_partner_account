import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.models.user import User
from app.schemas.file_upload import FilePresignedURL, FileUploadRead
from app.services.audit import audit_log
from app.services.s3_service import (
    delete_file_async,
    get_presigned_url,
    get_presigned_url_async,
    upload_file_async,
)

router = APIRouter(tags=["files"])


async def _check_client_access(db: AsyncSession, client_id: str, user: User) -> None:
    """Verify that the current user has access to the given client."""
    if user.role == "admin":
        return
    partner_row = await db.execute(select(Partner).where(Partner.user_id == user.id, Partner.deleted_at.is_(None)))
    partner = partner_row.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    client = await db.get(Client, client_id)
    if not client or str(client.partner_id) != str(partner.id):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Access denied"})


UPLOAD_MAX_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/files", response_model=list[FileUploadRead])
async def list_client_files(
    client_id: str = Query(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    await _check_client_access(db, client_id, current_user)
    result = await db.execute(
        select(FileUpload).where(FileUpload.client_id == client_id).order_by(FileUpload.created_at.desc())
    )
    records = result.scalars().all()
    # Presign — чисто CPU (HMAC), без сетевых вызовов. Вызываем синхронно,
    # чтобы не плодить task-switch'ы через asyncio.to_thread в цикле.
    return [
        FileUploadRead(
            file_id=str(r.id),
            url=get_presigned_url(r.s3_key),
            filename=r.original_name,
            size=r.size,
            mime_type=r.mime_type,
            document_type=r.document_type,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post("/upload", response_model=FileUploadRead, status_code=201)
@limiter.limit("10/minute")
async def upload_endpoint(
    request: Request,
    file: UploadFile,
    client_id: str,
    document_type: str = "other",
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    await _check_client_access(db, client_id, current_user)
    if not file.filename:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FILE", "message": "No filename"})

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Extension {ext} not allowed"},
        )

    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"MIME {content_type} not allowed"},
        )

    data = await file.read()
    if len(data) > UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": f"Max size is {UPLOAD_MAX_SIZE_MB} MB"},
        )

    s3_key = await upload_file_async(data, file.filename, content_type)

    # Atomicity: if DB commit fails after the S3 upload, remove the orphaned object.
    try:
        record = FileUpload(
            client_id=client_id,
            document_type=document_type,
            original_name=file.filename,
            s3_key=s3_key,
            size=len(data),
            mime_type=content_type,
        )
        db.add(record)
        await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_file_async(s3_key)
        raise

    url = await get_presigned_url_async(s3_key)

    audit_log(action="upload_file", target_id=str(record.id), target_type="file")

    return FileUploadRead(
        file_id=str(record.id),
        url=url,
        filename=record.original_name,
        size=record.size,
        mime_type=record.mime_type,
        document_type=record.document_type,
        created_at=record.created_at,
    )


@router.get("/files/{file_id}", response_model=FilePresignedURL)
async def get_file_url(
    file_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    record = await db.get(FileUpload, file_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "File not found"})
    await _check_client_access(db, str(record.client_id), current_user)
    url = await get_presigned_url_async(record.s3_key)
    return FilePresignedURL(file_id=str(record.id), url=url, filename=record.original_name)


@router.delete("/files/{file_id}", status_code=204)
async def delete_file_endpoint(
    file_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    record = await db.get(FileUpload, file_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "File not found"})
    await _check_client_access(db, str(record.client_id), current_user)
    # Delete DB row first; if that succeeds, remove S3 object. If S3 delete fails,
    # we keep the DB row deleted and rely on a periodic sweep to clean orphans.
    s3_key = record.s3_key
    record_id = str(record.id)
    await db.delete(record)
    await db.commit()
    try:
        await delete_file_async(s3_key)
    except Exception as e:  # noqa: BLE001
        import structlog

        structlog.get_logger().warning("s3_delete_failed", s3_key=s3_key, error=str(e))
    audit_log(action="delete_file", target_id=record_id, target_type="file")
