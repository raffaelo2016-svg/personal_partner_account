"""Provision stage-4 deal fields. Dry-run is the default; use ``--apply``."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.clients import CLIENT_DEAL_ADD_EVENT, CLIENT_DEAL_FIELDS, CLIENT_EVENT_HANDLER
from app.integrations.bitrix24.documents import TIMELINE_COMMENT_ADD_EVENT, TIMELINE_EVENT_HANDLER
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.survey_cli import _stored_credentials

ENTITY_ID = "CRM_DEAL"


@dataclass(frozen=True)
class FieldDefinition:
    key: str
    user_type_id: str
    label: str


FIELD_DEFINITIONS = (
    FieldDefinition("region", "string", "Регион клиента ЮРИТЕХ"),
    FieldDefinition("arbitrage_court", "string", "Арбитражный суд ЮРИТЕХ"),
    FieldDefinition("case_number", "string", "Номер дела ЮРИТЕХ"),
    FieldDefinition("court_date", "date", "Дата судебной процедуры ЮРИТЕХ"),
    FieldDefinition("client_type", "string", "Тип клиента ЮРИТЕХ"),
    FieldDefinition("client_status", "string", "Статус клиента ЮРИТЕХ"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the Bitrix24 stage-4 client projection")
    parser.add_argument("--apply", action="store_true", help="Create missing deal fields")
    return parser.parse_args()


async def _existing_field_names(client: Bitrix24Client) -> set[str]:
    result = await client.call("crm.deal.fields")
    if not isinstance(result, dict):
        return set()
    return {str(field_name).upper() for field_name in result}


async def _provision_field(client: Bitrix24Client, definition: FieldDefinition) -> None:
    await client.call(
        "userfieldconfig.add",
        {
            "moduleId": "crm",
            "field": {
                "entityId": ENTITY_ID,
                "fieldName": CLIENT_DEAL_FIELDS[definition.key],
                "userTypeId": definition.user_type_id,
                "multiple": "N",
                "mandatory": "N",
                "showFilter": "N",
                "editFormLabel": {"ru": definition.label},
                "listColumnLabel": {"ru": definition.label},
            },
        },
    )


async def _event_is_bound(client: Bitrix24Client, event_name: str, handler: str) -> bool:
    result = await client.call("event.get")
    events = result if isinstance(result, list) else []
    return any(
        isinstance(item, dict)
        and str(item.get("event") or item.get("EVENT") or "").upper() == event_name
        and str(item.get("handler") or item.get("HANDLER") or "").rstrip("/") == handler.rstrip("/")
        for item in events
    )


async def run(*, apply: bool) -> None:
    async with async_session() as db:
        installation = await active_installation(db)
        if installation is None:
            raise SystemExit("Active Bitrix24 installation not found")
        endpoint, token, _ = await _stored_credentials(db, settings.BITRIX_ALLOWED_DOMAIN)

    # On-prem portals may rebuild CRM field metadata during creation and need
    # longer than the regular operational request timeout.
    async with Bitrix24Client(endpoint, token, timeout=60.0) as client:
        existing = await _existing_field_names(client)
        missing = [item for item in FIELD_DEFINITIONS if CLIENT_DEAL_FIELDS[item.key] not in existing]
        event_bound = await _event_is_bound(client, CLIENT_DEAL_ADD_EVENT, CLIENT_EVENT_HANDLER)
        document_event_bound = await _event_is_bound(
            client,
            TIMELINE_COMMENT_ADD_EVENT,
            TIMELINE_EVENT_HANDLER,
        )
        if apply:
            for definition in missing:
                await _provision_field(client, definition)
            if not event_bound:
                await client.call("event.bind", {"event": CLIENT_DEAL_ADD_EVENT, "handler": CLIENT_EVENT_HANDLER})
            if not document_event_bound:
                await client.call(
                    "event.bind",
                    {"event": TIMELINE_COMMENT_ADD_EVENT, "handler": TIMELINE_EVENT_HANDLER},
                )

    print(f"client_deal_fields_{'created' if apply else 'missing'}={len(missing)}")
    print(f"client_deal_add_event_{'bound' if event_bound or apply else 'missing'}={int(event_bound or apply)}")
    print(
        "timeline_comment_add_event_"
        f"{'bound' if document_event_bound or apply else 'missing'}={int(document_event_bound or apply)}"
    )


def main() -> None:
    args = _parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
