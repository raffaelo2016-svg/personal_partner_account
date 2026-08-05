from __future__ import annotations

import argparse
import asyncio
import base64
import json
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.clients import (
    CLIENT_CONTACT_ENTITY_TYPE,
    CLIENT_DEAL_CATEGORY_ID,
    CLIENT_DEAL_ENTITY_TYPE,
    CLIENT_DEAL_FIELDS,
    CLIENT_DEAL_STAGE_ID,
    schedule_client_creation,
)
from app.integrations.bitrix24.documents import FILE_ENTITY_TYPE, file_marker, schedule_file_creation
from app.integrations.bitrix24.partners import PARTNER_ENTITY_TYPE, active_installation, schedule_partner_creation
from app.integrations.bitrix24.sync import _access_token, process_outbox_operation
from app.integrations.bitrix24.tasks import TASK_ENTITY_TYPE, schedule_task_creation
from app.models.bitrix_sync import BitrixEntityMap, BitrixInboundEvent, BitrixOutboxOperation
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.models.task import Task
from app.models.user import User
from app.services.s3_service import delete_file_async, download_file_async, upload_file_async
from app.validation.files import has_valid_signature


async def _process_one(db: AsyncSession, local_id: uuid.UUID, entity_type: str) -> None:
    operation = await db.scalar(
        select(BitrixOutboxOperation).where(
            BitrixOutboxOperation.local_entity_id == local_id,
            BitrixOutboxOperation.local_entity_type == entity_type,
        )
    )
    if operation is None:
        raise RuntimeError(f"OUTBOX_MISSING:{entity_type}")
    operation.status = "processing"
    operation.locked_at = datetime.now(UTC)
    await db.commit()
    if not await process_outbox_operation(db, operation):
        raise RuntimeError(f"OUTBOX_FAILED:{entity_type}:{operation.error_code}")


async def _recover_remote_ids(
    remote: Bitrix24Client,
    *,
    partner_id: uuid.UUID,
    client_id: uuid.UUID,
    smoke_id: uuid.UUID,
    deal_id: str | None,
    marker: str,
    remote_ids: dict[str, str | None],
) -> None:
    if not remote_ids["partner"]:
        result = await remote.call(
            "crm.item.list",
            {
                "entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
                "filter": {"=xmlId": str(partner_id)},
                "select": ["id", "xmlId"],
            },
        )
        items = result.get("items", []) if isinstance(result, dict) else []
        if items and isinstance(items[0], dict):
            remote_ids["partner"] = str(items[0].get("id") or items[0].get("ID") or "") or None

    for key, method in (("contact", "crm.contact.list"), ("deal", "crm.deal.list")):
        if remote_ids[key]:
            continue
        result = await remote.call(
            method,
            {
                "filter": {"=ORIGINATOR_ID": "partner_cabinet", "=ORIGIN_ID": str(client_id)},
                "select": ["ID"],
            },
        )
        if isinstance(result, list) and result and isinstance(result[0], dict):
            remote_ids[key] = str(result[0].get("ID") or result[0].get("id") or "") or None

    if not remote_ids["task"]:
        result = await remote.call(
            "tasks.task.list",
            {
                "filter": {"XML_ID": f"partner_cabinet:{smoke_id}"},
                "select": ["ID", "XML_ID"],
            },
        )
        tasks = result.get("tasks", []) if isinstance(result, dict) else []
        if tasks and isinstance(tasks[0], dict):
            remote_ids["task"] = str(tasks[0].get("id") or tasks[0].get("ID") or "") or None

    timeline_deal_id = remote_ids["deal"] or deal_id
    if not remote_ids["comment"] and timeline_deal_id:
        comments = await remote.list_all(
            "crm.timeline.comment.list",
            {
                "filter": {"ENTITY_ID": timeline_deal_id, "ENTITY_TYPE": "deal"},
                "select": ["ID", "COMMENT", "FILES"],
                "order": {"ID": "DESC"},
            },
            max_pages=5,
        )
        for comment in comments:
            if isinstance(comment, dict) and marker in str(comment.get("COMMENT") or comment.get("comment") or ""):
                remote_ids["comment"] = str(comment.get("ID") or comment.get("id") or "") or None
                files = comment.get("FILES") or comment.get("files") or []
                if files and isinstance(files[0], dict):
                    remote_ids["disk_file"] = str(files[0].get("ID") or files[0].get("id") or "") or None
                break


async def _remote_cleanup(
    remote: Bitrix24Client,
    *,
    partner_id: uuid.UUID,
    client_id: uuid.UUID,
    smoke_id: uuid.UUID,
    deal_id: str | None,
    marker: str,
    remote_ids: dict[str, str | None],
) -> None:
    await _recover_remote_ids(
        remote,
        partner_id=partner_id,
        client_id=client_id,
        smoke_id=smoke_id,
        deal_id=deal_id,
        marker=marker,
        remote_ids=remote_ids,
    )
    calls = (
        ("tasks.task.delete", {"taskId": remote_ids["task"]} if remote_ids["task"] else None),
        ("crm.timeline.comment.delete", {"id": remote_ids["comment"]} if remote_ids["comment"] else None),
        ("disk.file.delete", {"id": remote_ids["disk_file"]} if remote_ids["disk_file"] else None),
        (
            "crm.timeline.comment.delete",
            {"id": remote_ids["reverse_comment"]} if remote_ids["reverse_comment"] else None,
        ),
        ("crm.activity.delete", {"id": remote_ids["reverse_activity"]} if remote_ids["reverse_activity"] else None),
        (
            "disk.file.delete",
            {"id": remote_ids["reverse_disk_file"]} if remote_ids["reverse_disk_file"] else None,
        ),
        ("crm.deal.delete", {"id": remote_ids["reverse_deal"]} if remote_ids["reverse_deal"] else None),
        (
            "crm.contact.delete",
            {"id": remote_ids["reverse_contact"]} if remote_ids["reverse_contact"] else None,
        ),
        ("crm.deal.delete", {"id": remote_ids["deal"]} if remote_ids["deal"] else None),
        ("crm.contact.delete", {"id": remote_ids["contact"]} if remote_ids["contact"] else None),
        (
            "crm.item.delete",
            {"entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID, "id": remote_ids["partner"]}
            if remote_ids["partner"]
            else None,
        ),
    )
    errors: list[str] = []
    for method, params in calls:
        if params is None:
            continue
        try:
            await remote.call(method, params)
        except Bitrix24Error as exc:
            if "NOT_FOUND" not in exc.code.upper():
                errors.append(f"{method}:{exc.code[:40]}")
    if errors:
        raise RuntimeError(";".join(errors))


async def _create_and_verify_reverse_client(
    remote: Bitrix24Client,
    *,
    partner_id: uuid.UUID,
    partner_remote_id: str,
    remote_ids: dict[str, str | None],
) -> uuid.UUID:
    contact_result = await remote.call(
        "crm.contact.add",
        {
            "fields": {
                "LAST_NAME": "[SMOKE]",
                "NAME": "Входящий",
                "SECOND_NAME": "Клиент",
            }
        },
    )
    remote_ids["reverse_contact"] = str(contact_result)
    deal_result = await remote.call(
        "crm.deal.add",
        {
            "fields": {
                "TITLE": "[SMOKE] Обратный импорт клиента",
                "CATEGORY_ID": CLIENT_DEAL_CATEGORY_ID,
                "STAGE_ID": CLIENT_DEAL_STAGE_ID,
                "CONTACT_ID": remote_ids["reverse_contact"],
                f"PARENT_ID_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}": partner_remote_id,
                CLIENT_DEAL_FIELDS["client_type"]: "before_court",
                CLIENT_DEAL_FIELDS["client_status"]: "documents_collection",
            }
        },
    )
    remote_ids["reverse_deal"] = str(deal_result)

    for _ in range(20):
        await asyncio.sleep(1)
        async with async_session() as db:
            imported = await db.scalar(select(Client).where(Client.bitrix_deal_id == remote_ids["reverse_deal"]))
            if imported is None:
                continue
            if (
                imported.partner_id != partner_id
                or imported.bitrix_contact_id != remote_ids["reverse_contact"]
                or imported.full_name != "[SMOKE] Входящий Клиент"
                or imported.type != "before_court"
                or imported.status != "documents_collection"
            ):
                raise RuntimeError("REVERSE_CLIENT_MISMATCH")
            return imported.id
    raise RuntimeError("REVERSE_CLIENT_NOT_IMPORTED")


async def _create_and_verify_reverse_document(
    remote: Bitrix24Client,
    *,
    client_id: uuid.UUID,
    deal_id: str,
    remote_ids: dict[str, str | None],
) -> tuple[uuid.UUID, str]:
    content = b"%PDF-1.7\n% reverse smoke\n"
    result = await remote.call(
        "crm.timeline.comment.add",
        {
            "fields": {
                "ENTITY_ID": deal_id,
                "ENTITY_TYPE": "deal",
                "COMMENT": "[SMOKE] Обратный импорт документа",
                "FILES": [["reverse-smoke.pdf", base64.b64encode(content).decode("ascii")]],
            }
        },
    )
    remote_ids["reverse_comment"] = str(result)
    created = await remote.call("crm.timeline.comment.get", {"id": remote_ids["reverse_comment"]})
    files = created.get("FILES") if isinstance(created, dict) else None
    file_items = list(files.values()) if isinstance(files, dict) else files if isinstance(files, list) else []
    if not file_items or not isinstance(file_items[0], dict):
        raise RuntimeError("REVERSE_DOCUMENT_REMOTE_FILE_MISSING")
    remote_ids["reverse_disk_file"] = str(file_items[0].get("id") or file_items[0].get("ID") or "") or None

    for _ in range(30):
        await asyncio.sleep(1)
        async with async_session() as db:
            imported = await db.scalar(
                select(FileUpload).where(
                    FileUpload.client_id == client_id,
                    FileUpload.bitrix_timeline_comment_id == remote_ids["reverse_comment"],
                )
            )
            if imported is None:
                continue
            if (
                imported.original_name != "reverse-smoke.pdf"
                or imported.bitrix_disk_file_id != remote_ids["reverse_disk_file"]
                or imported.bitrix_sync_status != "synced"
            ):
                raise RuntimeError("REVERSE_DOCUMENT_MISMATCH")
            if await download_file_async(imported.s3_key) != content:
                raise RuntimeError("REVERSE_DOCUMENT_CONTENT_MISMATCH")
            return imported.id, imported.s3_key
    async with async_session() as db:
        receipt = await db.scalar(
            select(BitrixInboundEvent).where(
                BitrixInboundEvent.remote_entity_type == "timeline_comment",
                BitrixInboundEvent.remote_entity_id == remote_ids["reverse_comment"],
            )
        )
        if receipt is None:
            raise RuntimeError("REVERSE_DOCUMENT_EVENT_NOT_RECEIVED")
        raise RuntimeError(f"REVERSE_DOCUMENT_IMPORT_FAILED:{receipt.status}:{receipt.error_code or 'NO_ERROR_CODE'}")


async def _wait_for_manual_reverse_document(
    remote: Bitrix24Client,
    *,
    client_id: uuid.UUID,
    deal_id: str,
    remote_ids: dict[str, str | None],
) -> tuple[uuid.UUID, str]:
    print(
        json.dumps(
            {
                "manual_reverse_document": {
                    "deal_id": deal_id,
                    "deal_url": f"https://{settings.BITRIX_ALLOWED_DOMAIN}/crm/deal/details/{deal_id}/",
                    "filename": "reverse-smoke.pdf",
                    "comment": "[SMOKE] Ручной обратный импорт документа",
                }
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    # The Bitrix24 web uploader can take several minutes before the timeline
    # comment is committed, especially on a busy production portal.
    for _ in range(1800):
        await asyncio.sleep(1)
        async with async_session() as db:
            imported = await db.scalar(
                select(FileUpload).where(
                    FileUpload.client_id == client_id,
                    # Bitrix24 Disk appends " (1)", " (2)", ... when the
                    # synthetic filename already exists in its shared storage.
                    FileUpload.original_name.like("reverse-smoke%.pdf"),
                    or_(
                        FileUpload.bitrix_timeline_comment_id.is_not(None),
                        FileUpload.bitrix_activity_id.is_not(None),
                    ),
                )
            )
            if imported is None:
                continue
            if not imported.bitrix_disk_file_id or imported.bitrix_sync_status != "synced":
                raise RuntimeError("MANUAL_REVERSE_DOCUMENT_MISMATCH")
            if not has_valid_signature(await download_file_async(imported.s3_key), ".pdf"):
                raise RuntimeError("MANUAL_REVERSE_DOCUMENT_CONTENT_MISMATCH")
            remote_ids["reverse_comment"] = imported.bitrix_timeline_comment_id
            remote_ids["reverse_activity"] = imported.bitrix_activity_id
            remote_ids["reverse_disk_file"] = imported.bitrix_disk_file_id
            return imported.id, imported.s3_key

    activities = await remote.list_all(
        "crm.activity.list",
        {
            "filter": {"OWNER_TYPE_ID": 2, "OWNER_ID": deal_id},
            "select": ["ID", "DESCRIPTION", "FILES", "STORAGE_ELEMENT_IDS"],
            "order": {"ID": "DESC"},
        },
        max_pages=5,
    )
    for activity in activities:
        if not isinstance(activity, dict) or "[SMOKE] Ручной обратный импорт документа" not in str(
            activity.get("DESCRIPTION") or activity.get("description") or ""
        ):
            continue
        remote_ids["reverse_activity"] = str(activity.get("ID") or activity.get("id") or "") or None
        raw_files = activity.get("FILES") or activity.get("STORAGE_ELEMENT_IDS") or []
        file_items = (
            list(raw_files.values())
            if isinstance(raw_files, dict)
            else raw_files
            if isinstance(raw_files, list)
            else []
        )
        if file_items:
            first = file_items[0]
            remote_ids["reverse_disk_file"] = (
                str((first.get("ID") or first.get("id")) if isinstance(first, dict) else first) or None
            )
        break

    comments = await remote.list_all(
        "crm.timeline.comment.list",
        {
            "filter": {"ENTITY_ID": deal_id, "ENTITY_TYPE": "deal"},
            "select": ["ID", "COMMENT", "FILES"],
            "order": {"ID": "DESC"},
        },
        max_pages=5,
    )
    for comment in comments:
        if not isinstance(comment, dict) or "[SMOKE] Ручной обратный импорт документа" not in str(
            comment.get("COMMENT") or comment.get("comment") or ""
        ):
            continue
        remote_ids["reverse_comment"] = str(comment.get("ID") or comment.get("id") or "") or None
        files = comment.get("FILES") or comment.get("files") or []
        file_items = list(files.values()) if isinstance(files, dict) else files if isinstance(files, list) else []
        if file_items and isinstance(file_items[0], dict):
            remote_ids["reverse_disk_file"] = str(file_items[0].get("ID") or file_items[0].get("id") or "") or None
        break

    inbound_type = "crm_activity" if remote_ids["reverse_activity"] else "timeline_comment"
    inbound_id = remote_ids["reverse_activity"] or remote_ids["reverse_comment"]
    if inbound_id:
        async with async_session() as db:
            receipt = await db.scalar(
                select(BitrixInboundEvent).where(
                    BitrixInboundEvent.remote_entity_type == inbound_type,
                    BitrixInboundEvent.remote_entity_id == inbound_id,
                )
            )
            if receipt is not None:
                raise RuntimeError(
                    f"MANUAL_REVERSE_DOCUMENT_IMPORT_FAILED:{receipt.status}:{receipt.error_code or 'NO_ERROR_CODE'}"
                )
    raise RuntimeError("MANUAL_REVERSE_DOCUMENT_EVENT_NOT_RECEIVED")


async def run_smoke(*, manual_reverse_document: bool = False) -> dict[str, str]:
    partner_id = uuid.uuid4()
    client_id = uuid.uuid4()
    smoke_id = uuid.uuid4()
    user_id = uuid.uuid4()
    marker = file_marker(smoke_id)
    local_ids = (partner_id, client_id, smoke_id, user_id)
    s3_key: str | None = None
    installation_found = False
    remote_cleanup_error: str | None = None
    reverse_client_id: uuid.UUID | None = None
    reverse_document_id: uuid.UUID | None = None
    reverse_document_s3_key: str | None = None
    remote_ids: dict[str, str | None] = {
        "partner": None,
        "contact": None,
        "deal": None,
        "task": None,
        "comment": None,
        "disk_file": None,
        "reverse_contact": None,
        "reverse_deal": None,
        "reverse_comment": None,
        "reverse_activity": None,
        "reverse_disk_file": None,
    }

    try:
        async with async_session() as db:
            installation = await active_installation(db)
            if installation is None:
                raise RuntimeError("INSTALLATION_NOT_FOUND")
            installation_found = True

            user = User(
                id=user_id,
                email=f"smoke-{user_id}@example.invalid",
                hashed_password="disabled",
                role="partner",
                is_active=False,
            )
            partner = Partner(
                id=partner_id,
                user_id=user_id,
                partner_type="individual",
                company_name="[SMOKE] Синтетический партнёр",
                director_name="Тестов Тест Тестович",
                inn="7700000000",
                phone="+70000000000",
                status="active",
            )
            client = Client(
                id=client_id,
                partner_id=partner_id,
                type="before_court",
                status="documents_collection",
                full_name="[SMOKE] Клиент Тестовый",
            )
            db.add_all([user, partner, client])
            await db.flush()

            if not await schedule_partner_creation(db, partner):
                raise RuntimeError(f"PARTNER_NOT_QUEUED:{partner.bitrix_sync_error_code}")
            await _process_one(db, partner_id, PARTNER_ENTITY_TYPE)
            await db.refresh(partner)
            remote_ids["partner"] = partner.bitrix_partner_item_id

            if not await schedule_client_creation(db, client, partner=partner):
                raise RuntimeError(f"CLIENT_NOT_QUEUED:{client.bitrix_sync_error_code}")
            await _process_one(db, client_id, CLIENT_CONTACT_ENTITY_TYPE)
            await db.refresh(client)
            remote_ids["contact"] = client.bitrix_contact_id
            await _process_one(db, client_id, CLIENT_DEAL_ENTITY_TYPE)
            await db.refresh(client)
            remote_ids["deal"] = client.bitrix_deal_id

            token = await _access_token(db, installation)
            async with Bitrix24Client(installation.client_endpoint, token) as remote:
                reverse_client_id = await _create_and_verify_reverse_client(
                    remote,
                    partner_id=partner_id,
                    partner_remote_id=str(remote_ids["partner"]),
                    remote_ids=remote_ids,
                )

            task = Task(
                id=smoke_id,
                client_id=client_id,
                title="[SMOKE] Проверка интеграции",
                description="Синтетическая проверка; объект будет удалён автоматически.",
                priority="low",
                assigned_to="partner",
                created_by=user_id,
                due_date=date.today() + timedelta(days=1),
            )
            file_data = b"%PDF-1.4\n% smoke\n"
            s3_key = await upload_file_async(file_data, "smoke.pdf", "application/pdf")
            record = FileUpload(
                id=smoke_id,
                client_id=client_id,
                document_type="smoke_test",
                original_name="smoke.pdf",
                s3_key=s3_key,
                size=len(file_data),
                mime_type="application/pdf",
            )
            db.add_all([task, record])
            await db.flush()
            if not await schedule_task_creation(db, task):
                raise RuntimeError(f"TASK_NOT_QUEUED:{task.bitrix_sync_error_code}")
            if not await schedule_file_creation(db, record):
                raise RuntimeError(f"FILE_NOT_QUEUED:{record.bitrix_sync_error_code}")
            await _process_one(db, smoke_id, TASK_ENTITY_TYPE)
            await db.refresh(task)
            remote_ids["task"] = task.bitrix_task_id
            await _process_one(db, smoke_id, FILE_ENTITY_TYPE)
            await db.refresh(record)
            remote_ids["comment"] = record.bitrix_timeline_comment_id
            remote_ids["disk_file"] = record.bitrix_disk_file_id
            if task.bitrix_sync_status != "synced" or record.bitrix_sync_status != "synced":
                raise RuntimeError("PROJECTION_NOT_SYNCED")

            token = await _access_token(db, installation)
            async with Bitrix24Client(installation.client_endpoint, token) as remote:
                if manual_reverse_document:
                    reverse_document_id, reverse_document_s3_key = await _wait_for_manual_reverse_document(
                        remote,
                        client_id=client_id,
                        deal_id=str(remote_ids["deal"]),
                        remote_ids=remote_ids,
                    )
                else:
                    reverse_document_id, reverse_document_s3_key = await _create_and_verify_reverse_document(
                        remote,
                        client_id=client_id,
                        deal_id=str(remote_ids["deal"]),
                        remote_ids=remote_ids,
                    )
    finally:
        if installation_found:
            async with async_session() as db:
                installation = await active_installation(db)
                if installation is not None:
                    try:
                        token = await _access_token(db, installation)
                        async with Bitrix24Client(installation.client_endpoint, token) as remote:
                            await _remote_cleanup(
                                remote,
                                partner_id=partner_id,
                                client_id=client_id,
                                smoke_id=smoke_id,
                                deal_id=remote_ids["deal"],
                                marker=marker,
                                remote_ids=remote_ids,
                            )
                    except Exception as exc:  # noqa: BLE001
                        remote_cleanup_error = type(exc).__name__

                await db.execute(delete(BitrixEntityMap).where(BitrixEntityMap.local_entity_id.in_(local_ids)))
                await db.execute(
                    delete(BitrixOutboxOperation).where(BitrixOutboxOperation.local_entity_id.in_(local_ids))
                )
                if remote_ids["reverse_deal"]:
                    await db.execute(
                        delete(BitrixInboundEvent).where(
                            BitrixInboundEvent.remote_entity_type == CLIENT_DEAL_ENTITY_TYPE,
                            BitrixInboundEvent.remote_entity_id == remote_ids["reverse_deal"],
                        )
                    )
                if reverse_client_id:
                    await db.execute(delete(CourtFee).where(CourtFee.client_id == reverse_client_id))
                    await db.execute(
                        delete(BitrixEntityMap).where(BitrixEntityMap.local_entity_id == reverse_client_id)
                    )
                    await db.execute(delete(Client).where(Client.id == reverse_client_id))
                if reverse_document_id:
                    await db.execute(
                        delete(BitrixEntityMap).where(BitrixEntityMap.local_entity_id == reverse_document_id)
                    )
                    await db.execute(delete(FileUpload).where(FileUpload.id == reverse_document_id))
                if remote_ids["reverse_comment"]:
                    await db.execute(
                        delete(BitrixInboundEvent).where(
                            BitrixInboundEvent.remote_entity_type == "timeline_comment",
                            BitrixInboundEvent.remote_entity_id == remote_ids["reverse_comment"],
                        )
                    )
                if remote_ids["reverse_activity"]:
                    await db.execute(
                        delete(BitrixInboundEvent).where(
                            BitrixInboundEvent.remote_entity_type == "crm_activity",
                            BitrixInboundEvent.remote_entity_id == remote_ids["reverse_activity"],
                        )
                    )
                await db.execute(delete(Task).where(Task.id == smoke_id))
                await db.execute(delete(FileUpload).where(FileUpload.id == smoke_id))
                await db.execute(delete(Client).where(Client.id == client_id))
                await db.execute(delete(Partner).where(Partner.id == partner_id))
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        if s3_key:
            await delete_file_async(s3_key)
        if reverse_document_s3_key:
            await delete_file_async(reverse_document_s3_key)

    if remote_cleanup_error:
        raise RuntimeError(f"REMOTE_CLEANUP_FAILED:{remote_cleanup_error}")
    return {
        "status": "ok",
        "partner": "created_and_removed",
        "client": "created_and_removed",
        "reverse_client": "created_and_removed",
        "task": "created_and_removed",
        "document": "created_and_removed",
        "reverse_document": "created_and_removed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a PII-free Bitrix24 production acceptance smoke")
    parser.add_argument(
        "--manual-reverse-document",
        action="store_true",
        help="Wait for reverse-smoke.pdf added by a signed-in employee in the Bitrix24 deal UI",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(run_smoke(manual_reverse_document=args.manual_reverse_document)),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
