"""Routing chat attachments into client documents.

Partners sometimes send client papers in the chat instead of uploading them to
the client card. This service builds the admin inbox of such files and copies a
selected attachment into a regular ``FileUpload`` record, so the existing
document pipeline (card, checklist, Bitrix24 Disk/timeline) keeps working.
"""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Conflict, Forbidden, NotFound
from app.models.chat import ChatMessage, ChatRoom
from app.models.chat_attachment_assignment import ChatAttachmentAssignment
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.schemas.chat_documents import (
    ChatDocumentAssignmentRead,
    ChatDocumentCandidate,
    ChatDocumentInboxItem,
    ChatDocumentInboxResponse,
)
from app.services.audit import audit_log
from app.services.s3_service import download_file_async, get_presigned_url, upload_file_async

logger = structlog.get_logger()

InboxStatus = Literal["unassigned", "assigned", "ignored", "all"]

# Keep the API and the "document type" dropdown in sync.
DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "passport": "Паспорт",
    "snils": "СНИЛС",
    "inn_certificate": "Свидетельство ИНН",
    "children_birth_cert": "Свидетельство о рождении детей",
    "marriage_cert": "Свидетельство о браке/расторжении",
    "employment_history": "Справка о трудовой деятельности",
    "pension_account": "Справка о лицевом счёте ПФ",
    "tax_registry": "Выписка ЕГРН",
    "no_ip_status": "Справка об отсутствии ИП",
    "ndfl_2": "Справки 2-НДФЛ",
    "tax_debt": "Справка об исполнении обязанностей по налогам",
    "credit_debt": "Справка о задолженности по кредитам",
    "credit_agreements": "Копии кредитных договоров",
    "court_fee": "Квитанция госпошлины",
    "criminal_record": "Справка о судимости",
    "deposit_payment": "Квитанция на депозит",
    "uritech_review": "На проверку от ЮРИТЕХ",
    "other": "Прочее",
}
ASSIGNABLE_DOCUMENT_TYPES = frozenset(DOCUMENT_TYPE_LABELS)

MIN_CANDIDATE_SCORE = 40
MAX_CANDIDATES = 3


def _normalize(value: str | None) -> str:
    """Lowercase, ё → е, punctuation → space (keeps name matching tolerant)."""
    if not value:
        return ""
    lowered = value.casefold().replace("ё", "е")
    cleaned = [ch if ch.isalnum() else " " for ch in lowered]
    return " ".join("".join(cleaned).split())


def _score_client(full_name: str, *, file_norm: str, text_norm: str) -> tuple[int, str | None]:
    """Heuristic relevance of one client for an attachment (0..98)."""
    tokens = [token for token in _normalize(full_name).split() if len(token) >= 3]
    if not tokens:
        return 0, None

    surname = tokens[0]
    # Инициалы в ФИО вида «Иванов И. И.» дают односимвольные токены — они
    # совпадают почти с любым текстом, поэтому учитываем только слова.
    rest = [token for token in tokens[1:] if len(token) >= 2]
    best_score = 0
    matched_on: str | None = None
    for haystack, base, label in ((file_norm, 60, "filename"), (text_norm, 45, "text")):
        if not haystack or surname not in haystack:
            continue
        score = base
        if rest and rest[0] in haystack:
            score += 15
        if len(rest) > 1 and rest[1] in haystack:
            score += 8
        if score > best_score:
            best_score = score
            matched_on = label
    return min(best_score, 98), matched_on


def _sender_label(message: ChatMessage) -> str:
    if message.sender_type == "user":
        return "Партнёр"
    if message.sender_type == "admin":
        return "Из Битрикс24" if message.origin == "bitrix" else "Сотрудник"
    return "Система"


def _document_type_label(document_type: str | None) -> str:
    if not document_type:
        return "документ"
    return DOCUMENT_TYPE_LABELS.get(document_type, document_type)


def _item_status(assignment: ChatAttachmentAssignment | None) -> Literal["unassigned", "assigned", "ignored"]:
    if assignment is None:
        return "unassigned"
    if assignment.status == "ignored":
        return "ignored"
    return "assigned"


def _assignment_read(
    assignment: ChatAttachmentAssignment,
    *,
    client_name: str | None,
    file: FileUpload | None,
) -> ChatDocumentAssignmentRead:
    return ChatDocumentAssignmentRead(
        message_id=str(assignment.chat_message_id),
        status="assigned" if assignment.status == "assigned" else "ignored",
        client_id=str(assignment.client_id) if assignment.client_id else None,
        client_name=client_name,
        document_type=assignment.document_type,
        file_id=str(assignment.file_id) if assignment.file_id else None,
        assigned_at=assignment.assigned_at,
        bitrix_sync_status=file.bitrix_sync_status if file else None,
        bitrix_sync_error_code=file.bitrix_sync_error_code if file else None,
    )


def _attachment_payload(message: ChatMessage) -> dict:
    filename = message.attachment_filename or "файл"
    return {
        "url": get_presigned_url(message.attachment_s3_key or "", filename=message.attachment_filename),
        "filename": filename,
        "size": message.attachment_size,
        "mime_type": message.attachment_mime_type,
    }


def _base_query() -> Select:
    return (
        select(ChatMessage, ChatRoom, Partner, ChatAttachmentAssignment, Client)
        .join(ChatRoom, ChatMessage.room_id == ChatRoom.id)
        .join(Partner, ChatRoom.partner_id == Partner.id)
        .outerjoin(
            ChatAttachmentAssignment,
            ChatAttachmentAssignment.chat_message_id == ChatMessage.id,
        )
        .outerjoin(Client, ChatAttachmentAssignment.client_id == Client.id)
    )


def _apply_filters(
    stmt: Select,
    *,
    status: InboxStatus = "unassigned",
    partner_id: str | None = None,
    search: str | None = None,
) -> Select:
    stmt = stmt.where(
        ChatMessage.attachment_s3_key.is_not(None),
        ChatMessage.deleted_at.is_(None),
        ChatMessage.sender_type != "bot",
    )
    if partner_id:
        stmt = stmt.where(ChatRoom.partner_id == partner_id)
    if status == "unassigned":
        stmt = stmt.where(ChatAttachmentAssignment.id.is_(None))
    elif status == "assigned":
        stmt = stmt.where(ChatAttachmentAssignment.status == "assigned")
    elif status == "ignored":
        stmt = stmt.where(ChatAttachmentAssignment.status == "ignored")
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ChatMessage.attachment_filename.ilike(pattern),
                ChatMessage.text.ilike(pattern),
                Partner.company_name.ilike(pattern),
                Client.full_name.ilike(pattern),
            )
        )
    return stmt


async def _clients_by_partner(db: AsyncSession, partner_ids: set[uuid.UUID]) -> dict[uuid.UUID, list[Client]]:
    if not partner_ids:
        return {}
    rows = (
        await db.execute(
            select(Client)
            .where(
                Client.partner_id.in_(partner_ids),
                Client.deleted_at.is_(None),
            )
            .order_by(Client.full_name.asc())
        )
    ).scalars()
    grouped: dict[uuid.UUID, list[Client]] = {}
    for client in rows:
        grouped.setdefault(client.partner_id, []).append(client)
    return grouped


def _candidates_for(
    clients: list[Client],
    *,
    filename: str | None,
    text: str | None,
) -> list[ChatDocumentCandidate]:
    file_norm = _normalize(filename)
    text_norm = _normalize(text)
    found: list[ChatDocumentCandidate] = []
    for client in clients:
        score, matched_on = _score_client(client.full_name, file_norm=file_norm, text_norm=text_norm)
        if matched_on is None or score < MIN_CANDIDATE_SCORE:
            continue
        found.append(
            ChatDocumentCandidate(
                client_id=str(client.id),
                full_name=client.full_name,
                status=client.status,
                score=score,
                matched_on=matched_on,  # type: ignore[arg-type]
            )
        )
    found.sort(key=lambda item: (-item.score, item.full_name))
    return found[:MAX_CANDIDATES]


async def _files_map(db: AsyncSession, file_ids: set[uuid.UUID]) -> dict[uuid.UUID, FileUpload]:
    if not file_ids:
        return {}
    rows = (await db.execute(select(FileUpload).where(FileUpload.id.in_(file_ids)))).scalars()
    return {row.id: row for row in rows}


def _to_item(
    message: ChatMessage,
    room: ChatRoom,
    partner: Partner,
    assignment: ChatAttachmentAssignment | None,
    client: Client | None,
    *,
    candidates: list[ChatDocumentCandidate],
    file: FileUpload | None,
) -> ChatDocumentInboxItem:
    return ChatDocumentInboxItem(
        message_id=str(message.id),
        room_id=str(room.id),
        partner_id=str(partner.id),
        partner_name=partner.company_name,
        sender_type=message.sender_type,
        sender_label=_sender_label(message),
        text=message.text,
        created_at=message.created_at,
        attachment=_attachment_payload(message),  # type: ignore[arg-type]
        status=_item_status(assignment),
        candidates=candidates,
        assignment=(
            _assignment_read(assignment, client_name=client.full_name if client else None, file=file)
            if assignment is not None
            else None
        ),
    )


async def list_inbox(
    db: AsyncSession,
    *,
    status: InboxStatus = "unassigned",
    partner_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ChatDocumentInboxResponse:
    stmt = _apply_filters(_base_query(), status=status, partner_id=partner_id, search=search)

    total = (
        await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar() or 0

    rows = (
        await db.execute(
            stmt.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    partner_ids = {row[2].id for row in rows}
    clients_map = await _clients_by_partner(db, partner_ids)
    files = await _files_map(
        db,
        {row[3].file_id for row in rows if row[3] is not None and row[3].file_id is not None},
    )

    items = [
        _to_item(
            message,
            room,
            partner,
            assignment,
            client,
            candidates=_candidates_for(
                clients_map.get(partner.id, []),
                filename=message.attachment_filename,
                text=message.text,
            ),
            file=files.get(assignment.file_id) if assignment is not None and assignment.file_id else None,
        )
        for message, room, partner, assignment, client in rows
    ]

    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return ChatDocumentInboxResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        page_size=page_size,
    )


async def get_inbox_item(db: AsyncSession, message_id: str) -> ChatDocumentInboxItem:
    row = (
        await db.execute(_base_query().where(ChatMessage.id == message_id))
    ).first()
    if row is None:
        raise NotFound("Chat message not found")
    message, room, partner, assignment, client = row
    if not message.attachment_s3_key:
        raise NotFound("Chat message has no attachment")

    clients_map = await _clients_by_partner(db, {partner.id})
    file = await db.get(FileUpload, assignment.file_id) if assignment is not None and assignment.file_id else None
    return _to_item(
        message,
        room,
        partner,
        assignment,
        client,
        candidates=_candidates_for(
            clients_map.get(partner.id, []),
            filename=message.attachment_filename,
            text=message.text,
        ),
        file=file,
    )


async def count_unassigned(db: AsyncSession) -> int:
    stmt = _apply_filters(_base_query(), status="unassigned")
    return (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar() or 0


async def _get_message_with_room(db: AsyncSession, message_id: str) -> tuple[ChatMessage, ChatRoom]:
    message = await db.get(ChatMessage, message_id)
    if message is None or message.deleted_at is not None:
        raise NotFound("Chat message not found")
    if not message.attachment_s3_key:
        raise BadRequest("Chat message has no attachment")
    room = await db.get(ChatRoom, message.room_id)
    if room is None:
        raise NotFound("Chat room not found")
    return message, room


async def assign_attachment(
    db: AsyncSession,
    *,
    message_id: str,
    client_id: str,
    document_type: str,
    assigned_by: uuid.UUID,
    sync_to_bitrix: bool = True,
) -> tuple[ChatDocumentAssignmentRead, ChatMessage]:
    """Copy a chat attachment into the client card and return the system note."""
    if document_type not in ASSIGNABLE_DOCUMENT_TYPES:
        raise BadRequest("Unknown document type")

    message, room = await _get_message_with_room(db, message_id)

    client = await db.get(Client, client_id)
    if client is None or client.deleted_at is not None:
        raise NotFound("Client not found")
    if str(client.partner_id) != str(room.partner_id):
        raise Forbidden("Client belongs to another partner")

    existing = await db.scalar(
        select(ChatAttachmentAssignment).where(
            ChatAttachmentAssignment.chat_message_id == message.id,
        )
    )
    if existing is not None and existing.status == "assigned":
        raise Conflict("Документ уже привязан к клиенту")

    try:
        data = await download_file_async(message.attachment_s3_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat_attachment_download_failed", message_id=message_id, error=str(exc))
        raise BadRequest("Не удалось прочитать файл из хранилища") from exc

    content_sha256 = hashlib.sha256(data).hexdigest()
    file_record = await db.scalar(
        select(FileUpload).where(
            FileUpload.client_id == client.id,
            FileUpload.content_sha256 == content_sha256,
        )
    )
    duplicate = file_record is not None
    created_s3_key: str | None = None

    if file_record is None:
        original_name = message.attachment_filename or "документ"
        mime_type = (
            message.attachment_mime_type
            or mimetypes.guess_type(original_name)[0]
            or "application/octet-stream"
        )
        try:
            created_s3_key = await upload_file_async(data, original_name, mime_type)
            file_record = FileUpload(
                client_id=client.id,
                document_type=document_type,
                original_name=original_name,
                s3_key=created_s3_key,
                size=len(data),
                mime_type=mime_type,
                content_sha256=content_sha256,
            )
            db.add(file_record)
            await db.flush()
            if sync_to_bitrix:
                from app.integrations.bitrix24.documents import schedule_file_creation

                await schedule_file_creation(db, file_record)
        except Exception:
            if created_s3_key is not None:
                from app.services.s3_service import delete_file_async

                try:
                    await delete_file_async(created_s3_key)
                except Exception as cleanup_error:  # noqa: BLE001
                    logger.warning("chat_attachment_cleanup_failed", s3_key=created_s3_key, error=str(cleanup_error))
            raise

    assigned_at = datetime.now(UTC)
    if existing is None:
        assignment = ChatAttachmentAssignment(
            chat_message_id=message.id,
            client_id=client.id,
            file_id=file_record.id,
            document_type=document_type,
            status="assigned",
            assigned_by=assigned_by,
            assigned_at=assigned_at,
        )
        db.add(assignment)
    else:
        assignment = existing
        assignment.client_id = client.id
        assignment.file_id = file_record.id
        assignment.document_type = document_type
        assignment.status = "assigned"
        assignment.assigned_by = assigned_by
        assignment.assigned_at = assigned_at

    note = ChatMessage(
        room_id=room.id,
        sender_id=None,
        sender_type="system",
        text=(
            f"Документ «{message.attachment_filename or 'файл'}» прикреплён "
            f"к клиенту {client.full_name} · {_document_type_label(document_type)}"
        ),
        delivery_status="sent",
        origin="cabinet",
    )
    db.add(note)
    await db.flush()

    audit_log(
        action="chat_attachment_assigned",
        user_id=str(assigned_by),
        target_id=str(message.id),
        target_type="chat_message",
        details={
            "client_id": str(client.id),
            "file_id": str(file_record.id),
            "document_type": document_type,
            "duplicate": duplicate,
            "sync_to_bitrix": sync_to_bitrix,
        },
    )
    logger.info(
        "chat_attachment_assigned",
        message_id=str(message.id),
        client_id=str(client.id),
        duplicate=duplicate,
    )

    return (
        _assignment_read(assignment, client_name=client.full_name, file=file_record),
        note,
    )


async def ignore_attachment(
    db: AsyncSession,
    *,
    message_id: str,
    assigned_by: uuid.UUID,
) -> ChatDocumentAssignmentRead:
    message, _room = await _get_message_with_room(db, message_id)
    existing = await db.scalar(
        select(ChatAttachmentAssignment).where(
            ChatAttachmentAssignment.chat_message_id == message.id,
        )
    )
    if existing is not None and existing.status == "assigned":
        raise Conflict("Документ уже привязан к клиенту")

    assigned_at = datetime.now(UTC)
    if existing is None:
        assignment = ChatAttachmentAssignment(
            chat_message_id=message.id,
            status="ignored",
            assigned_by=assigned_by,
            assigned_at=assigned_at,
        )
        db.add(assignment)
    else:
        assignment = existing
        assignment.status = "ignored"
        assignment.client_id = None
        assignment.file_id = None
        assignment.document_type = None
        assignment.assigned_by = assigned_by
        assignment.assigned_at = assigned_at
    await db.flush()

    audit_log(
        action="chat_attachment_ignored",
        user_id=str(assigned_by),
        target_id=str(message.id),
        target_type="chat_message",
    )
    return _assignment_read(assignment, client_name=None, file=None)
