"""Audit trail service for critical actions.

Logs critical actions to structlog AND persists to DB via fire-and-forget task.
"""

import asyncio

import structlog

logger = structlog.get_logger("audit")


async def _persist(
    action: str,
    user_id: str | None,
    target_id: str | None,
    target_type: str | None,
    details: dict | None,
    ip_address: str | None,
) -> None:
    from app.database import async_session
    from app.models.audit_log import AuditLog

    try:
        async with async_session() as session:
            entry = AuditLog(
                action=action,
                user_id=user_id,
                target_id=target_id,
                target_type=target_type,
                ip_address=ip_address,
                details=details,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("audit_persist_failed", action=action, error=str(e))


def audit_log(
    action: str,
    *,
    user_id: str | None = None,
    target_id: str | None = None,
    target_type: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Log an auditable action to stdout AND DB (fire-and-forget)."""
    logger.info(
        "audit_event",
        action=action,
        user_id=user_id,
        target_id=target_id,
        target_type=target_type,
        details=details or {},
        ip_address=ip_address,
    )
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist(action, user_id, target_id, target_type, details, ip_address))
    except RuntimeError:
        # No running loop (e.g. Celery sync task) — skip DB persistence.
        pass
