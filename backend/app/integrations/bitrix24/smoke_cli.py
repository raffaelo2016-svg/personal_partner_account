from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select

from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.documents import FILE_ENTITY_TYPE, file_marker, schedule_file_creation
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.sync import _access_token, process_outbox_operation
from app.integrations.bitrix24.tasks import TASK_ENTITY_TYPE, schedule_task_creation
from app.models.bitrix_sync import BitrixEntityMap, BitrixOutboxOperation
from app.models.client import Client
from app.models.file_upload import FileUpload
from app.models.partner import Partner
from app.models.task import Task
from app.services.s3_service import delete_file_async, upload_file_async


async def _remote_cleanup(
    remote: Bitrix24Client,
    *,
    task_id: str | None,
    task_xml_id: str,
    comment_id: str | None,
    disk_file_id: str | None,
    deal_id: str,
    marker: str,
) -> None:
    if not task_id:
        result = await remote.call(
            "tasks.task.list",
            {"filter": {"XML_ID": task_xml_id}, "select": ["ID", "XML_ID"]},
        )
        tasks = result.get("tasks", []) if isinstance(result, dict) else []
        if tasks and isinstance(tasks[0], dict):
            task_id = str(tasks[0].get("id") or tasks[0].get("ID") or "") or None
    if not comment_id:
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
            if isinstance(comment, dict) and marker in str(comment.get("COMMENT") or comment.get("comment") or ""):
                comment_id = str(comment.get("ID") or comment.get("id") or "") or None
                files = comment.get("FILES") or comment.get("files") or []
                if files and isinstance(files[0], dict):
                    disk_file_id = str(files[0].get("ID") or files[0].get("id") or "") or None
                break

    for method, params in (
        ("tasks.task.delete", {"taskId": task_id} if task_id else None),
        ("crm.timeline.comment.delete", {"id": comment_id} if comment_id else None),
        ("disk.file.delete", {"id": disk_file_id} if disk_file_id else None),
    ):
        if params is None:
            continue
        try:
            await remote.call(method, params)
        except Bitrix24Error as exc:
            if "NOT_FOUND" not in exc.code.upper():
                raise


async def run_smoke() -> dict[str, str]:
    smoke_id = uuid.uuid4()
    s3_key: str | None = None
    task: Task | None = None
    record: FileUpload | None = None
    installation = None
    deal_id = ""
    task_xml_id = f"partner_cabinet:{smoke_id}"
    marker = file_marker(smoke_id)
    task_id: str | None = None
    comment_id: str | None = None
    disk_file_id: str | None = None
    remote_cleanup_error: str | None = None

    try:
        async with async_session() as db:
            row = (
                await db.execute(
                    select(Client, Partner)
                    .join(Partner, Partner.id == Client.partner_id)
                    .where(
                        Client.deleted_at.is_(None),
                        Client.bitrix_sync_status == "synced",
                        Client.bitrix_deal_id.is_not(None),
                        Partner.deleted_at.is_(None),
                        Partner.status == "active",
                    )
                    .order_by(Client.created_at)
                    .limit(1)
                )
            ).first()
            installation = await active_installation(db)
            if row is None or installation is None:
                raise RuntimeError("SMOKE_PREREQUISITES_NOT_FOUND")
            client, partner = row
            deal_id = str(client.bitrix_deal_id)

            task = Task(
                id=smoke_id,
                client_id=client.id,
                title="[SMOKE] Проверка интеграции",
                description="Синтетическая проверка; объект будет удалён автоматически.",
                priority="low",
                assigned_to="partner",
                created_by=partner.user_id,
                due_date=date.today() + timedelta(days=1),
            )
            s3_key = await upload_file_async(b"%PDF-1.4\n% smoke\n", "smoke.pdf", "application/pdf")
            record = FileUpload(
                id=smoke_id,
                client_id=client.id,
                document_type="smoke_test",
                original_name="smoke.pdf",
                s3_key=s3_key,
                size=17,
                mime_type="application/pdf",
            )
            db.add_all([task, record])
            await db.flush()
            if not await schedule_task_creation(db, task):
                raise RuntimeError(f"TASK_NOT_QUEUED:{task.bitrix_sync_error_code}")
            if not await schedule_file_creation(db, record):
                raise RuntimeError(f"FILE_NOT_QUEUED:{record.bitrix_sync_error_code}")
            operations = list(
                (
                    await db.scalars(
                        select(BitrixOutboxOperation).where(
                            BitrixOutboxOperation.local_entity_id == smoke_id,
                            BitrixOutboxOperation.local_entity_type.in_((TASK_ENTITY_TYPE, FILE_ENTITY_TYPE)),
                        )
                    )
                ).all()
            )
            if len(operations) != 2:
                raise RuntimeError("OUTBOX_OPERATION_COUNT_INVALID")
            for operation in operations:
                operation.status = "processing"
                operation.locked_at = datetime.now(UTC)
            await db.commit()

            for operation in operations:
                if not await process_outbox_operation(db, operation):
                    raise RuntimeError(f"OUTBOX_FAILED:{operation.local_entity_type}:{operation.error_code}")
            await db.refresh(task)
            await db.refresh(record)
            if task.bitrix_sync_status != "synced" or record.bitrix_sync_status != "synced":
                raise RuntimeError("PROJECTION_NOT_SYNCED")
            task_id = task.bitrix_task_id
            comment_id = record.bitrix_timeline_comment_id
            disk_file_id = record.bitrix_disk_file_id
    finally:
        if installation is not None:
            async with async_session() as db:
                current_installation = await active_installation(db)
                if current_installation is not None:
                    try:
                        token = await _access_token(db, current_installation)
                        async with Bitrix24Client(current_installation.client_endpoint, token) as remote:
                            await _remote_cleanup(
                                remote,
                                task_id=task_id,
                                task_xml_id=task_xml_id,
                                comment_id=comment_id,
                                disk_file_id=disk_file_id,
                                deal_id=deal_id,
                                marker=marker,
                            )
                    except Exception as exc:  # noqa: BLE001
                        remote_cleanup_error = type(exc).__name__

                await db.execute(delete(BitrixEntityMap).where(BitrixEntityMap.local_entity_id == smoke_id))
                await db.execute(delete(BitrixOutboxOperation).where(BitrixOutboxOperation.local_entity_id == smoke_id))
                await db.execute(delete(Task).where(Task.id == smoke_id))
                await db.execute(delete(FileUpload).where(FileUpload.id == smoke_id))
                await db.commit()
        if s3_key:
            await delete_file_async(s3_key)

    if remote_cleanup_error:
        raise RuntimeError(f"REMOTE_CLEANUP_FAILED:{remote_cleanup_error}")
    return {"status": "ok", "task": "created_and_removed", "document": "created_and_removed"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a PII-free Bitrix24 production acceptance smoke")
    parser.parse_args()
    print(json.dumps(asyncio.run(run_smoke()), ensure_ascii=False))


if __name__ == "__main__":
    main()
