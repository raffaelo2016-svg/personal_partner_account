import hashlib

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.database import get_db
from app.integrations.bitrix24.documents import schedule_file_creation, sync_client_initial_documents
from app.models.client import Client
from app.models.file_deletion_tombstone import FileDeletionTombstone
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
from app.validation.files import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    file_extension,
    has_valid_signature,
    max_file_size_for_filename,
    normalize_mime_type,
)

router = APIRouter(tags=["files"])
logger = structlog.get_logger()


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


UPLOAD_MAX_SIZE_MB = MAX_FILE_SIZE_BYTES // (1024 * 1024)
_has_valid_signature = has_valid_signature


def _read_response(record: FileUpload, url: str) -> FileUploadRead:
    return FileUploadRead(
        file_id=str(record.id),
        url=url,
        filename=record.original_name,
        size=record.size,
        mime_type=record.mime_type,
        document_type=record.document_type,
        created_at=record.created_at,
        bitrix_sync_status=record.bitrix_sync_status,
        bitrix_sync_error_code=record.bitrix_sync_error_code,
        bitrix_disk_file_id=record.bitrix_disk_file_id,
    )


@router.get("/files", response_model=list[FileUploadRead])
async def list_client_files(
    client_id: str = Query(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    await _check_client_access(db, client_id, current_user)
    try:
        await sync_client_initial_documents(db, client_id)
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning(
            "bitrix_initial_documents_sync_failed",
            client_id=client_id,
            error_type=type(exc).__name__,
        )
    result = await db.execute(
        select(FileUpload).where(FileUpload.client_id == client_id).order_by(FileUpload.created_at.desc())
    )
    records = result.scalars().all()
    # Presign — чисто CPU (HMAC), без сетевых вызовов. Вызываем синхронно,
    # чтобы не плодить task-switch'ы через asyncio.to_thread в цикле.
    return [_read_response(r, get_presigned_url(r.s3_key, filename=r.original_name)) for r in records]


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

    ext = file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Extension {ext} not allowed"},
        )

    content_type = normalize_mime_type(file.filename, file.content_type)
    if content_type is None:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"MIME {file.content_type or ''} not allowed"},
        )

    max_size = max_file_size_for_filename(file.filename)
    data = await file.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": f"Max size is {max_size // (1024 * 1024)} MB"},
        )
    if not _has_valid_signature(data, ext):
        raise HTTPException(
            status_code=415,
            detail={"code": "INVALID_FILE_CONTENT", "message": "File content does not match its extension"},
        )

    content_sha256 = hashlib.sha256(data).hexdigest()
    duplicate = await db.scalar(
        select(FileUpload).where(
            FileUpload.client_id == client_id,
            FileUpload.content_sha256 == content_sha256,
        )
    )
    if duplicate is not None:
        return _read_response(
            duplicate, await get_presigned_url_async(duplicate.s3_key, filename=duplicate.original_name)
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
            content_sha256=content_sha256,
        )
        db.add(record)
        await db.flush()
        await schedule_file_creation(db, record)
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_file_async(s3_key)
        raise

    url = await get_presigned_url_async(s3_key, filename=record.original_name)

    audit_log(action="upload_file", target_id=str(record.id), target_type="file")

    return _read_response(record, url)


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
    url = await get_presigned_url_async(record.s3_key, filename=record.original_name)
    return FilePresignedURL(file_id=str(record.id), url=url, filename=record.original_name)


@router.post("/files/{file_id}/bitrix/retry", response_model=FileUploadRead)
async def retry_file_bitrix_endpoint(
    file_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    record = await db.get(FileUpload, file_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "File not found"})
    await _check_client_access(db, str(record.client_id), current_user)

    await schedule_file_creation(db, record, retry=True)
    await db.commit()
    url = await get_presigned_url_async(record.s3_key, filename=record.original_name)

    audit_log(action="retry_file_bitrix_sync", target_id=str(record.id), target_type="file")
    return _read_response(record, url)


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
    if record.bitrix_sync_status in {"pending", "processing"}:
        raise HTTPException(
            status_code=409,
            detail={"code": "BITRIX_SYNC_IN_PROGRESS", "message": "Document synchronization is in progress"},
        )
    # The Bitrix24 copy stays on the Disk and in the deal timeline by design, so a
    # tombstone keeps the folder/timeline reconciler from importing it back.
    if record.bitrix_disk_file_id:
        await db.execute(
            insert(FileDeletionTombstone)
            .values(client_id=record.client_id, bitrix_disk_file_id=record.bitrix_disk_file_id)
            .on_conflict_do_nothing(constraint="uq_file_deletion_tombstones_client_disk_file")
        )
    # Delete DB row first; if that succeeds, remove S3 object. If S3 delete fails,
    # we keep the DB row deleted and rely on a periodic sweep to clean orphans.
    s3_key = record.s3_key
    record_id = str(record.id)
    await db.delete(record)
    await db.commit()
    try:
        await delete_file_async(s3_key)
    except Exception as e:  # noqa: BLE001
        logger.warning("s3_delete_failed", s3_key=s3_key, error=str(e))
    audit_log(action="delete_file", target_id=record_id, target_type="file")
