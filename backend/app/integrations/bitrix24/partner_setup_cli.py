"""Provision stage-3 partner fields and the remote-update event subscription.

Dry-run is the default. Add ``--apply`` to create missing configuration.
No credentials or partner records are printed.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.partners import PARTNER_FIELDS, active_installation
from app.integrations.bitrix24.survey_cli import _stored_credentials

ENTITY_ID = "CRM_31"
EVENT_NAME = "ONCRMDYNAMICITEMUPDATE"
EVENT_HANDLER = "https://finzdorovie.ru/api/v1/integrations/bitrix24/handler"


@dataclass(frozen=True)
class FieldDefinition:
    key: str
    user_type_id: str
    label: str


FIELD_DEFINITIONS = (
    FieldDefinition("partner_type", "string", "Тип партнёра ЮРИТЕХ"),
    FieldDefinition("inn", "string", "ИНН партнёра ЮРИТЕХ"),
    FieldDefinition("kpp", "string", "КПП партнёра ЮРИТЕХ"),
    FieldDefinition("court_fee", "money", "Стоимость клиента ЮРИТЕХ"),
    FieldDefinition("payment_days", "integer", "Срок оплаты ЮРИТЕХ, дней"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the Bitrix24 stage-3 partner projection")
    parser.add_argument("--apply", action="store_true", help="Create missing fields and bind the update event")
    return parser.parse_args()


async def _existing_field_names(client: Bitrix24Client) -> set[str]:
    result = await client.call(
        "crm.item.fields",
        {"entityTypeId": settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID},
    )
    fields = result.get("fields", {}) if isinstance(result, dict) else {}
    if not isinstance(fields, dict):
        return set()

    names: set[str] = set()
    for field_key, field in fields.items():
        if not isinstance(field, dict):
            continue
        name = field.get("upperName") or field.get("fieldName") or field.get("FIELD_NAME") or field_key
        if name:
            names.add(str(name).upper())
    return names


async def _provision_field(client: Bitrix24Client, definition: FieldDefinition) -> None:
    full_name = PARTNER_FIELDS[definition.key]
    await client.call(
        "userfieldconfig.add",
        {
            "moduleId": "crm",
            "field": {
                "entityId": ENTITY_ID,
                "fieldName": full_name,
                "userTypeId": definition.user_type_id,
                "multiple": "N",
                "mandatory": "N",
                "showFilter": "N",
                "editFormLabel": {"ru": definition.label},
                "listColumnLabel": {"ru": definition.label},
            },
        },
    )


async def _event_is_bound(client: Bitrix24Client) -> bool:
    events = await client.call("event.get")
    if not isinstance(events, list):
        return False
    return any(
        isinstance(item, dict)
        and str(item.get("event") or item.get("EVENT") or "").upper() == EVENT_NAME
        and str(item.get("handler") or item.get("HANDLER") or "").rstrip("/") == EVENT_HANDLER.rstrip("/")
        for item in events
    )


async def run(*, apply: bool) -> None:
    async with async_session() as db:
        installation = await active_installation(db)
        if installation is None:
            raise SystemExit("Active Bitrix24 installation not found")
        endpoint, token, _ = await _stored_credentials(db, settings.BITRIX_ALLOWED_DOMAIN)

    async with Bitrix24Client(endpoint, token) as client:
        existing = await _existing_field_names(client)
        missing = [definition for definition in FIELD_DEFINITIONS if PARTNER_FIELDS[definition.key] not in existing]
        event_bound = await _event_is_bound(client)
        if apply:
            for definition in missing:
                await _provision_field(client, definition)
            if not event_bound:
                await client.call("event.bind", {"event": EVENT_NAME, "handler": EVENT_HANDLER})

    action = "created" if apply else "missing"
    print(f"partner_fields_{action}={len(missing)}")
    print(f"partner_update_event={'bound' if event_bound or apply else 'missing'}")


def main() -> None:
    args = _parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
