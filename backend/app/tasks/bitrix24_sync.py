from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import structlog
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.celery_app import celery
from app.config import settings
from app.database import async_session
from app.database import engine as async_engine
from app.integrations.bitrix24.chat import poll_chat_events, reconcile_chat_file_history
from app.integrations.bitrix24.clients import retry_client_deal_events
from app.integrations.bitrix24.documents import retry_document_events
from app.integrations.bitrix24.sync import claim_outbox_batch, process_outbox_operation, release_stale_operations
from app.integrations.bitrix24.tasks import reconcile_remote_tasks, retry_task_status_events
from app.models.bitrix_sync import BitrixEntityMap

logger = structlog.get_logger()
ResultT = TypeVar("ResultT")


async def _run_with_disposed_pool(awaitable: Awaitable[ResultT]) -> ResultT:
    """Run one Celery async unit and close its loop-bound DB pool afterwards."""
    try:
        return await awaitable
    finally:
        await async_engine.dispose()


def _run_async(awaitable: Awaitable[ResultT]) -> ResultT:
    """Keep pooled asyncpg connections from leaking across asyncio.run loops."""
    try:
        previous_loop = asyncio.get_event_loop()
    except RuntimeError:
        previous_loop = None

    try:
        return asyncio.run(_run_with_disposed_pool(awaitable))
    finally:
        if previous_loop is not None and not previous_loop.is_closed():
            asyncio.set_event_loop(previous_loop)


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
    result = _run_async(_process_ready_operations())
    logger.info("bitrix_outbox_batch_processed", **result)
    return result


async def _poll_chat_events() -> dict[str, int]:
    async with async_session() as db:
        return await poll_chat_events(db)


@celery.task(name="app.tasks.bitrix24_sync.poll_bitrix_chat_events")
def poll_bitrix_chat_events() -> dict[str, int]:
    try:
        result = _run_async(_poll_chat_events())
    except Exception as exc:
        logger.warning("bitrix_chat_poll_failed", error_type=type(exc).__name__)
        return {"received": 0, "imported": 0, "journaled": 0, "failed": 1}
    logger.info("bitrix_chat_events_polled", **result)
    return result


async def _reconcile_chat_files() -> dict[str, int]:
    async with async_session() as db:
        return await reconcile_chat_file_history(db)


@celery.task(name="app.tasks.bitrix24_sync.reconcile_bitrix_chat_files")
def reconcile_bitrix_chat_files() -> dict[str, int]:
    try:
        result = _run_async(_reconcile_chat_files())
    except Exception as exc:
        logger.warning("bitrix_chat_file_reconcile_failed", error_type=type(exc).__name__)
        return {"partners": 0, "scanned": 0, "imported": 0, "failed": 1}
    logger.info("bitrix_chat_files_reconciled", **result)
    return result


async def _release_stale() -> int:
    async with async_session() as db:
        return await release_stale_operations(db)


async def _retry_task_events() -> tuple[int, int]:
    async with async_session() as db:
        return await retry_task_status_events(db)


async def _reconcile_remote_tasks() -> dict[str, int]:
    async with async_session() as db:
        return await reconcile_remote_tasks(db, limit=settings.BITRIX_OUTBOX_BATCH_SIZE)


async def _retry_client_events() -> tuple[int, int]:
    async with async_session() as db:
        return await retry_client_deal_events(db)


async def _retry_document_events() -> tuple[int, int]:
    async with async_session() as db:
        return await retry_document_events(db)


async def _recover_interrupted_sync() -> tuple[
    int,
    tuple[int, int],
    dict[str, int],
    tuple[int, int],
    tuple[int, int],
]:
    """Run recovery steps on one event loop before disposing the shared async pool."""
    released = await _release_stale()
    task_events = await _retry_task_events()
    task_reconcile = await _reconcile_remote_tasks()
    client_events = await _retry_client_events()
    document_events = await _retry_document_events()
    return released, task_events, task_reconcile, client_events, document_events


@celery.task(name="app.tasks.bitrix24_sync.reconcile_bitrix_sync")
def reconcile_bitrix_sync() -> dict[str, int]:
    """Recover interrupted work and report stale mappings without exposing data."""
    released, task_events, task_reconcile, client_events, document_events = _run_async(_recover_interrupted_sync())
    task_events_claimed, task_events_completed = task_events
    client_events_claimed, client_events_completed = client_events
    document_events_claimed, document_events_completed = document_events
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
        "task_mappings_claimed": task_reconcile["claimed"],
        "task_mappings_completed": task_reconcile["completed"],
        "task_mappings_failed": task_reconcile["failed"],
        "client_events_claimed": client_events_claimed,
        "client_events_completed": client_events_completed,
        "document_events_claimed": document_events_claimed,
        "document_events_completed": document_events_completed,
    }
    logger.info("bitrix_sync_reconciled", **result)
    return result
