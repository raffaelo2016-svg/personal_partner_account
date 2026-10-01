from io import BytesIO
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequest
from app.database import get_db
from app.models.user import User
from app.schemas.client import ClientCreate, ClientRead, ClientStats, ClientUpdate
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.status import ChangeStatusRequest, StatusLogRead
from app.services.client_service import (
    _get_partner_id_for_user,
    create_client,
    delete_client,
    get_client,
    get_client_stats,
    list_clients,
    update_client,
)
from app.services.document_generation_service import DOCUMENT_FILENAMES, DOCX_MIME_TYPE, generate_document
from app.services.progress_service import get_progress
from app.services.status_machine import change_status, get_status_history

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=PaginatedResponse[ClientRead])
async def list_clients_endpoint(
    search: str | None = Query(None, max_length=100),  # noqa: B008
    type: str | None = Query(None),  # noqa: B008
    status: str | None = Query(None),  # noqa: B008
    category: str | None = Query(None),  # noqa: B008
    pagination: PaginationParams = Depends(),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    items, total = await list_clients(
        db,
        partner_id=partner_id,
        search=search,
        client_type=type,
        status=status,
        category=category,
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


@router.get("/stats", response_model=ClientStats)
async def client_stats_endpoint(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    return await get_client_stats(db, partner_id)


@router.get("/{client_id}", response_model=ClientRead)
async def get_client_endpoint(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    return await get_client(db, client_id, partner_id=partner_id)


@router.get("/{client_id}/documents/{document_kind}")
async def generate_client_document(
    client_id: str,
    document_kind: Literal["application", "creditors", "inventory"],
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    client = await get_client(db, client_id, partner_id=partner_id)
    if client.type != "before_court" or client.document_preparation_mode != "partner":
        raise BadRequest("Самостоятельная генерация не выбрана для этого клиента")
    content = generate_document(document_kind, client, client.document_generation_data)
    filename = DOCUMENT_FILENAMES[document_kind]
    return StreamingResponse(
        BytesIO(content),
        media_type=DOCX_MIME_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("", response_model=ClientRead, status_code=201)
async def create_client_endpoint(
    body: ClientCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    result = await create_client(db, partner_id, body)
    await db.commit()
    return result


@router.put("/{client_id}", response_model=ClientRead)
async def update_client_endpoint(
    client_id: str,
    body: ClientUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    result = await update_client(db, client_id, body, partner_id=partner_id)
    await db.commit()
    return result


@router.delete("/{client_id}", status_code=204)
async def delete_client_endpoint(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    await delete_client(db, client_id, partner_id=partner_id)
    await db.commit()


@router.post("/{client_id}/status", response_model=ClientRead)
async def change_client_status(
    client_id: str,
    body: ChangeStatusRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    client = await change_status(
        db,
        client_id,
        body.status,
        str(current_user.id),
        comment=body.comment,
        partner_id=partner_id,
    )
    await db.commit()
    await db.refresh(client)
    from app.services.client_service import _client_to_read

    return _client_to_read(client)


@router.get("/{client_id}/status-history", response_model=list[StatusLogRead])
async def get_client_status_history(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    logs = await get_status_history(db, client_id, partner_id=partner_id)
    return [
        StatusLogRead(
            id=log.id,
            client_id=str(log.client_id),
            from_status=log.from_status,
            to_status=log.to_status,
            changed_by=str(log.changed_by),
            comment=log.comment,
            changed_at=log.changed_at,
        )
        for log in logs
    ]


@router.get("/{client_id}/progress")
async def get_client_progress(
    client_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))
    return await get_progress(db, client_id, partner_id=partner_id)
