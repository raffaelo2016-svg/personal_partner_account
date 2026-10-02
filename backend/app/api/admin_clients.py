import hashlib
from io import BytesIO
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.core.exceptions import BadRequest
from app.database import get_db
from app.integrations.bitrix24.documents import schedule_file_creation
from app.models.file_upload import FileUpload
from app.models.notification import Notification
from app.models.partner import Partner
from app.schemas.client import ClientRead, ClientUpdate
from app.schemas.finance import CourtFeeRead
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.audit import audit_log
from app.services.client_service import get_client, list_clients, retry_client_bitrix_sync, update_client
from app.services.document_generation_service import DOCUMENT_FILENAMES, DOCX_MIME_TYPE, generate_document
from app.services.finance_service import list_court_fees
from app.services.notification_service import create_notification
from app.services.s3_service import delete_file_async, upload_file_async

router = APIRouter(prefix="/admin/clients", tags=["admin-clients"])

GENERATED_DOCUMENT_TYPES = {
    "application": "generated_application",
    "creditors": "generated_creditors",
    "inventory": "generated_inventory",
}


@router.get("", response_model=PaginatedResponse[ClientRead])
async def list_all_clients(
    search: str | None = Query(None, max_length=100),  # noqa: B008
    type: str | None = Query(None),  # noqa: B008
    status: str | None = Query(None),  # noqa: B008
    partner_id: str | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    items, total = await list_clients(
        db,
        partner_id=partner_id,
        search=search,
        client_type=type,
        status=status,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        pages=pages,
        page_size=pagination.page_size,
    )


@router.get("/{client_id}", response_model=ClientRead)
async def get_any_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    return await get_client(db, client_id)


@router.get("/{client_id}/fees", response_model=PaginatedResponse[CourtFeeRead])
async def client_fees(
    client_id: str,
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    items, total = await list_court_fees(
        db,
        client_id=client_id,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        pages=pages,
        page_size=pagination.page_size,
    )


@router.put("/{client_id}", response_model=ClientRead)
async def update_any_client(
    client_id: str,
    body: ClientUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    result = await update_client(db, client_id, body)
    await db.commit()
    return result


@router.post("/{client_id}/documents/{document_kind}")
async def generate_uritech_document(
    client_id: str,
    document_kind: Literal["application", "creditors", "inventory"],
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user=Depends(require_role("admin")),  # noqa: B008
):
    client = await get_client(db, client_id)
    if client.type != "before_court" or client.document_preparation_mode != "uritech":
        raise BadRequest("Подготовка документов ЮРИТЕХ не выбрана для этого клиента")

    content = generate_document(document_kind, client, client.document_generation_data)
    filename = DOCUMENT_FILENAMES[document_kind]
    document_type = GENERATED_DOCUMENT_TYPES[document_kind]
    content_sha256 = hashlib.sha256(content).hexdigest()
    existing = await db.scalar(
        select(FileUpload).where(
            FileUpload.client_id == client_id,
            FileUpload.content_sha256 == content_sha256,
        )
    )
    uploaded_s3_key: str | None = None

    try:
        if existing is None:
            uploaded_s3_key = await upload_file_async(content, filename, DOCX_MIME_TYPE)
            record = FileUpload(
                client_id=client_id,
                document_type=document_type,
                original_name=filename,
                s3_key=uploaded_s3_key,
                size=len(content),
                mime_type=DOCX_MIME_TYPE,
                content_sha256=content_sha256,
            )
            db.add(record)
            await db.flush()
            await schedule_file_creation(db, record)
        else:
            existing.document_type = document_type
            existing.original_name = filename
            await db.flush()

        generated_types = set(
            await db.scalars(
                select(FileUpload.document_type).where(
                    FileUpload.client_id == client_id,
                    FileUpload.document_type.in_(GENERATED_DOCUMENT_TYPES.values()),
                )
            )
        )
        if generated_types == set(GENERATED_DOCUMENT_TYPES.values()):
            partner = await db.get(Partner, client.partner_id)
            notification_link = f"/dashboard/clients/{client.id}#client-files"
            notification_exists = (
                await db.scalar(
                    select(Notification.id).where(
                        Notification.user_id == partner.user_id,
                        Notification.type == "court_documents_ready",
                        Notification.link == notification_link,
                    )
                )
                if partner
                else None
            )
            if partner and notification_exists is None:
                await create_notification(
                    db,
                    user_id=str(partner.user_id),
                    notif_type="court_documents_ready",
                    title="Документы клиента подготовлены",
                    message=f"Комплект документов для клиента «{client.full_name}» доступен в карточке.",
                    link=notification_link,
                )

        await db.commit()
    except Exception:
        await db.rollback()
        if uploaded_s3_key is not None:
            await delete_file_async(uploaded_s3_key)
        raise

    audit_log(
        action="generate_court_document",
        user_id=str(current_user.id),
        target_id=str(client.id),
        target_type="client",
        details={"document_kind": document_kind},
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=DOCX_MIME_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/{client_id}/bitrix/retry", response_model=ClientRead)
async def retry_client_bitrix(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user=Depends(require_role("admin")),  # noqa: B008
):
    result = await retry_client_bitrix_sync(db, client_id)
    await db.commit()
    return result
