from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.clients import CLIENT_DEAL_ENTITY_TYPE, process_client_deal_add_event
from app.integrations.bitrix24.documents import (
    CRM_ACTIVITY_ENTITY_TYPE,
    TIMELINE_COMMENT_ENTITY_TYPE,
    process_document_event,
)
from app.integrations.bitrix24.partners import mark_remote_partner_conflict
from app.integrations.bitrix24.sync import register_inbound_event
from app.integrations.bitrix24.tasks import process_task_status_event
from app.integrations.bitrix24.token_storage import TokenStorageError, decrypt_token, encrypt_token
from app.models.bitrix_installation import BitrixInstallation
from app.models.bitrix_sync import BitrixInboundEvent

logger = structlog.get_logger()
router = APIRouter(prefix="/integrations/bitrix24", tags=["bitrix24"])


async def _request_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Invalid payload")
        return body

    form = await request.form()
    payload: dict[str, Any] = {}
    auth: dict[str, str] = {}
    for key, value in form.multi_items():
        text_value = str(value)
        if key.startswith("auth[") and key.endswith("]"):
            auth[key[5:-1]] = text_value
        else:
            payload[key] = text_value
    if auth:
        payload["auth"] = auth
    return payload


def _auth_from(payload: dict[str, Any]) -> dict[str, str]:
    raw_auth = payload.get("auth")
    if not isinstance(raw_auth, dict):
        raise HTTPException(status_code=400, detail="Missing auth payload")
    auth = {str(key): str(value) for key, value in raw_auth.items() if value is not None}
    required = ("access_token", "refresh_token", "client_endpoint", "server_endpoint", "member_id")
    if any(not auth.get(key) for key in required):
        raise HTTPException(status_code=400, detail="Incomplete auth payload")
    return auth


def _validated_portal_domain(client_endpoint: str) -> str:
    parsed = urlparse(client_endpoint)
    domain = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or domain != settings.BITRIX_ALLOWED_DOMAIN.lower():
        raise HTTPException(status_code=403, detail="Portal is not allowed")
    return domain


def _token_expiry(auth: dict[str, str]) -> datetime | None:
    try:
        if auth.get("expires"):
            return datetime.fromtimestamp(int(auth["expires"]), tz=UTC)
        if auth.get("expires_in"):
            return datetime.now(UTC) + timedelta(seconds=int(auth["expires_in"]))
    except (TypeError, ValueError, OverflowError):
        return None
    return None


@router.post("/install")
async def install_bitrix24(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    payload = await _request_payload(request)
    auth = _auth_from(payload)
    portal_domain = _validated_portal_domain(auth["client_endpoint"])

    try:
        async with Bitrix24Client(auth["client_endpoint"], auth["access_token"]) as client:
            await client.call("app.info")
    except Bitrix24Error as exc:
        logger.warning("bitrix_install_verification_failed", portal_domain=portal_domain, error_code=exc.code)
        raise HTTPException(status_code=403, detail="Bitrix24 authorization verification failed") from exc

    try:
        values = {
            "portal_domain": portal_domain,
            "client_endpoint": auth["client_endpoint"],
            "server_endpoint": auth["server_endpoint"],
            "access_token_encrypted": await encrypt_token(db, auth["access_token"]),
            "refresh_token_encrypted": await encrypt_token(db, auth["refresh_token"]),
            "application_token_encrypted": (
                await encrypt_token(db, auth["application_token"]) if auth.get("application_token") else None
            ),
            "scope": auth.get("scope", ""),
            "status": auth.get("status", "L"),
            "installed_by_user_id": int(auth["user_id"]) if auth.get("user_id", "").isdigit() else None,
            "token_expires_at": _token_expiry(auth),
        }
    except TokenStorageError as exc:
        logger.error("bitrix_install_encryption_unavailable")
        raise HTTPException(status_code=503, detail="Token storage is not configured") from exc

    member_id = auth["member_id"]
    installation = await db.scalar(select(BitrixInstallation).where(BitrixInstallation.member_id == member_id))
    if installation is None:
        installation = BitrixInstallation(member_id=member_id, **values)
        db.add(installation)
    else:
        for field, value in values.items():
            setattr(installation, field, value)
    await db.commit()

    logger.info("bitrix_install_completed", portal_domain=portal_domain, member_id=member_id)
    return {"ok": True, "status": "installed"}


@router.get("/handler")
async def bitrix24_handler_status():
    return {"ok": True, "status": "ready"}


@router.post("/handler")
async def bitrix24_handler(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    payload = await _request_payload(request)
    auth = payload.get("auth") if isinstance(payload.get("auth"), dict) else {}
    member_id = str(auth.get("member_id") or payload.get("member_id") or "")
    application_token = str(auth.get("application_token") or payload.get("application_token") or "")
    if not member_id or not application_token:
        raise HTTPException(status_code=401, detail="Invalid event authorization")

    installation = await db.scalar(select(BitrixInstallation).where(BitrixInstallation.member_id == member_id))
    if installation is None or not installation.application_token_encrypted:
        raise HTTPException(status_code=401, detail="Unknown installation")
    try:
        expected_token = await decrypt_token(db, installation.application_token_encrypted)
    except TokenStorageError as exc:
        logger.error("bitrix_event_encryption_unavailable", member_id=member_id)
        raise HTTPException(status_code=503, detail="Event verification is unavailable") from exc
    if not hmac.compare_digest(application_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid event authorization")

    event_name = str(payload.get("event", "UNKNOWN"))[:100].upper()
    event_id, created = await register_inbound_event(db, member_id=member_id, payload=payload)
    conflict = False
    task_status_synced = False
    client_imported = False
    document_imported = False
    if created:
        conflict = await mark_remote_partner_conflict(
            db,
            member_id=member_id,
            event_name=event_name,
            payload=payload,
        )
        if conflict:
            await db.commit()
        if event_id:
            receipt = await db.get(BitrixInboundEvent, event_id)
            if receipt is not None:
                if receipt.remote_entity_type == "task":
                    task_status_synced = await process_task_status_event(db, receipt)
                elif receipt.remote_entity_type == CLIENT_DEAL_ENTITY_TYPE:
                    client_imported = await process_client_deal_add_event(db, receipt)
                elif receipt.remote_entity_type in {TIMELINE_COMMENT_ENTITY_TYPE, CRM_ACTIVITY_ENTITY_TYPE}:
                    document_imported = await process_document_event(db, receipt)
                await db.commit()
    logger.info(
        "bitrix_event_received",
        event=event_name,
        member_id=member_id,
        duplicate=not created,
        event_receipt_id=str(event_id) if event_id else None,
    )
    return {
        "ok": True,
        "duplicate": not created,
        "conflict": conflict,
        "task_status_synced": task_status_synced,
        "client_imported": client_imported,
        "document_imported": document_imported,
    }
