from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.models.bitrix_sync import BitrixOutboxOperation
from app.models.client import Client

PREPARATION_NOTICE_ENTITY_TYPE = "client_preparation_notice"
PREPARATION_NOTICE_TEXT = "Партнер сам готовит документы для подачи в суд."
PREPARATION_NOTICE_COMMENT = f"[B][COLOR=#FF0000]{PREPARATION_NOTICE_TEXT}[/COLOR][/B]"


async def schedule_preparation_notice(
    db: AsyncSession,
    *,
    client: Client,
    member_id: str,
    deal_id: str,
    category_id: Any,
    stage_id: Any,
) -> None:
    if (
        client.document_preparation_mode != "partner"
        or str(category_id) != str(settings.BITRIX_SUPPORT_DEAL_CATEGORY_ID)
        or stage_id != settings.BITRIX_SUPPORT_DEAL_STAGE_ID
    ):
        return
    await db.execute(
        insert(BitrixOutboxOperation)
        .values(
            id=uuid.uuid4(),
            member_id=member_id,
            operation_key=f"client:preparation-notice:{client.id}:{deal_id}:v1",
            local_entity_type=PREPARATION_NOTICE_ENTITY_TYPE,
            local_entity_id=client.id,
            bitrix_method="crm.timeline.comment.add",
            payload={"fields": {
                "ENTITY_ID": deal_id,
                "ENTITY_TYPE": "deal",
                "COMMENT": PREPARATION_NOTICE_COMMENT,
            }},
            correlation_id=uuid.uuid4(),
            max_attempts=settings.BITRIX_OUTBOX_MAX_ATTEMPTS,
        )
        .on_conflict_do_nothing(constraint="uq_bitrix_outbox_operation_key")
    )


async def execute_preparation_notice(remote: Bitrix24Client, operation: BitrixOutboxOperation) -> str:
    """Recover a comment accepted by Bitrix before a timeout without duplicating it."""
    fields = operation.payload["fields"]
    comments = await remote.list_all(
        "crm.timeline.comment.list",
        {
            "filter": {"ENTITY_ID": fields["ENTITY_ID"], "ENTITY_TYPE": "deal"},
            "select": ["ID", "COMMENT"],
            "order": {"ID": "DESC"},
        },
    )
    for comment in comments:
        if comment.get("COMMENT") == fields["COMMENT"] and comment.get("ID"):
            return str(comment["ID"])
    result = await remote.call(operation.bitrix_method, operation.payload)
    if not result or isinstance(result, bool) or not isinstance(result, str | int):
        raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return a preparation comment ID")
    return str(result)
