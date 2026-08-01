"""Configure stage-5 responsible mappings and the task update event."""

from __future__ import annotations

import argparse
import asyncio

from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.survey_cli import _stored_credentials
from app.integrations.bitrix24.tasks import (
    TASK_CREATOR_SETTING,
    TASK_EVENT_HANDLER,
    TASK_RESPONSIBLE_SETTING_PREFIX,
    TASK_UPDATE_EVENT,
)
from app.models.settings import SystemSetting


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the Bitrix24 stage-5 task projection")
    parser.add_argument("--apply", action="store_true", help="Save supplied mappings and bind the update event")
    parser.add_argument("--partner-responsible-id", type=int)
    parser.add_argument("--admin-responsible-id", type=int)
    parser.add_argument("--creator-id", type=int)
    return parser.parse_args()


async def _event_is_bound(client: Bitrix24Client) -> bool:
    events = await client.call("event.get")
    if not isinstance(events, list):
        return False
    return any(
        isinstance(item, dict)
        and str(item.get("event") or item.get("EVENT") or "").upper() == TASK_UPDATE_EVENT
        and str(item.get("handler") or item.get("HANDLER") or "").rstrip("/") == TASK_EVENT_HANDLER.rstrip("/")
        for item in events
    )


async def _active_user_ids(client: Bitrix24Client) -> set[int]:
    users = await client.list_all("user.get", {"FILTER": {"ACTIVE": True}})
    result: set[int] = set()
    for item in users:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("ID") or item.get("id") or "")
        if user_id.isdigit() and int(user_id) > 0:
            result.add(int(user_id))
    return result


async def _configured_ids() -> dict[str, int]:
    keys = {
        "partner": f"{TASK_RESPONSIBLE_SETTING_PREFIX}partner",
        "admin": f"{TASK_RESPONSIBLE_SETTING_PREFIX}admin",
        "creator": TASK_CREATOR_SETTING,
    }
    async with async_session() as db:
        result: dict[str, int] = {}
        for role, key in keys.items():
            setting = await db.get(SystemSetting, key)
            value = setting.value.strip() if setting else ""
            if value.isdigit() and int(value) > 0:
                result[role] = int(value)
        return result


async def _save_ids(values: dict[str, int]) -> None:
    keys = {
        "partner": f"{TASK_RESPONSIBLE_SETTING_PREFIX}partner",
        "admin": f"{TASK_RESPONSIBLE_SETTING_PREFIX}admin",
        "creator": TASK_CREATOR_SETTING,
    }
    async with async_session() as db:
        for role, value in values.items():
            key = keys[role]
            setting = await db.get(SystemSetting, key)
            if setting is None:
                db.add(SystemSetting(key=key, value=str(value)))
            else:
                setting.value = str(value)
        await db.commit()


async def run(*, apply: bool, supplied: dict[str, int | None]) -> None:
    async with async_session() as db:
        installation = await active_installation(db)
        if installation is None:
            raise SystemExit("Active Bitrix24 installation not found")
        endpoint, token, _ = await _stored_credentials(db, settings.BITRIX_ALLOWED_DOMAIN)

    async with Bitrix24Client(endpoint, token) as client:
        active_ids = await _active_user_ids(client)
        requested = {role: value for role, value in supplied.items() if value is not None}
        invalid = [role for role, value in requested.items() if value not in active_ids]
        if invalid:
            raise SystemExit("Configured Bitrix24 user IDs must belong to active users")
        event_bound = await _event_is_bound(client)
        if apply:
            await _save_ids(requested)
            if not event_bound:
                await client.call("event.bind", {"event": TASK_UPDATE_EVENT, "handler": TASK_EVENT_HANDLER})

    configured = await _configured_ids()
    valid = sum(value in active_ids for value in configured.values())
    print(f"task_responsible_roles_configured={sum(role in configured for role in ('partner', 'admin'))}")
    print(f"task_configured_users_valid={valid}/{len(configured)}")
    print(f"task_update_event={'bound' if event_bound or apply else 'missing'}")


def main() -> None:
    args = _parse_args()
    asyncio.run(
        run(
            apply=args.apply,
            supplied={
                "partner": args.partner_responsible_id,
                "admin": args.admin_responsible_id,
                "creator": args.creator_id,
            },
        )
    )


if __name__ == "__main__":
    main()
