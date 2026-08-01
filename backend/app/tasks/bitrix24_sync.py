from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.celery_app import celery
from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.sync import claim_outbox_batch, process_outbox_operation, release_stale_operations
from app.integrations.bitrix24.tasks import retry_task_status_events
from app.models.bitrix_sync import BitrixEntityMap

logger = structlog.get_logger()


async def _process_ready_operations() -> dict[str, int]:
    completed = 0
    failed_or_retried = 0
    async with async_session() as db:
        operations = await claim_outbox_batch(db)
        for operation in operations:
            if await process_outbox_operation(db, operation):
                completed += 1
            else:
                failed_or_retried += 1
    return {"claimed": len(operations), "completed": completed, "failed_or_retried": failed_or_retried}


@celery.task(name="app.tasks.bitrix24_sync.process_bitrix_outbox")
def process_bitrix_outbox() -> dict[str, int]:
    result = asyncio.run(_process_ready_operations())
    logger.info("bitrix_outbox_batch_processed", **result)
    return result


async def _release_stale() -> int:
    async with async_session() as db:
        return await release_stale_operations(db)


async def _retry_task_events() -> tuple[int, int]:
    async with async_session() as db:
        return await retry_task_status_events(db)


@celery.task(name="app.tasks.bitrix24_sync.reconcile_bitrix_sync")
def reconcile_bitrix_sync() -> dict[str, int]:
    """Recover interrupted work and report stale mappings without exposing data."""
    released = asyncio.run(_release_stale())
    task_events_claimed, task_events_completed = asyncio.run(_retry_task_events())
    engine = create_engine(settings.sync_database_url)
    stale_before = datetime.now(UTC) - timedelta(hours=settings.BITRIX_RECONCILE_AFTER_HOURS)
    try:
        with Session(engine) as session:
            stale_mappings = session.scalar(
                select(func.count(BitrixEntityMap.id)).where(
                    (BitrixEntityMap.last_verified_at.is_(None)) | (BitrixEntityMap.last_verified_at < stale_before)
                )
            )
    finally:
        engine.dispose()
    result = {
        "released_operations": released,
        "stale_mappings": int(stale_mappings or 0),
        "task_events_claimed": task_events_claimed,
        "task_events_completed": task_events_completed,
    }
    logger.info("bitrix_sync_reconciled", **result)
    return result
