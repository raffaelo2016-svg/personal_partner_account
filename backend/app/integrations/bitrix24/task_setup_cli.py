"""Configure task responsible mappings and inbound task events."""

from __future__ import annotations

import argparse
import asyncio

from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.partners import active_installation
from app.integrations.bitrix24.survey_cli import _stored_credentials
from app.integrations.bitrix24.tasks import (
    TASK_ADD_EVENT,
    TASK_AUDITORS_SETTING,
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
    parser.add_argument("--auditor-ids", type=int, nargs="+")
    parser.add_argument(
        "--fill-missing-with-installer",
        action="store_true",
        help="Use the active integration installer only for roles that are not configured yet",
    )
    return parser.parse_args()


async def _event_is_bound(client: Bitrix24Client, event_name: str) -> bool:
    events = await client.call("event.get")
    if not isinstance(events, list):
        return False
    return any(
        isinstance(item, dict)
        and str(item.get("event") or item.get("EVENT") or "").upper() == event_name
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


async def _configured_auditor_ids() -> list[int]:
    async with async_session() as db:
        setting = await db.get(SystemSetting, TASK_AUDITORS_SETTING)
        value = setting.value if setting else ""
        return [
            int(item) for item in value.replace(",", " ").split() if item.isdigit() and int(item) > 0
        ]


async def _save_ids(values: dict[str, int], *, auditor_ids: list[int] | None = None) -> None:
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
        if auditor_ids is not None:
            setting = await db.get(SystemSetting, TASK_AUDITORS_SETTING)
            value = ",".join(str(user_id) for user_id in dict.fromkeys(auditor_ids))
            if setting is None:
                db.add(SystemSetting(key=TASK_AUDITORS_SETTING, value=value))
            else:
                setting.value = value
        await db.commit()


def _values_to_apply(
    supplied: dict[str, int | None],
    configured: dict[str, int],
    *,
    fill_missing_with_installer: bool,
    installer_id: int | None,
) -> dict[str, int]:
    values = {role: value for role, value in supplied.items() if value is not None}
    if not fill_missing_with_installer or installer_id is None:
        return values
    for role in ("partner", "admin", "creator"):
        if role not in configured:
            values.setdefault(role, installer_id)
    return values


async def run(
    *,
    apply: bool,
    supplied: dict[str, int | None],
    auditor_ids: list[int] | None = None,
    fill_missing_with_installer: bool = False,
) -> None:
    async with async_session() as db:
        installation = await active_installation(db)
        if installation is None:
            raise SystemExit("Active Bitrix24 installation not found")
        installer_id = installation.installed_by_user_id
        endpoint, token, _ = await _stored_credentials(db, settings.BITRIX_ALLOWED_DOMAIN)

    configured = await _configured_ids()
    async with Bitrix24Client(endpoint, token) as client:
        active_ids = await _active_user_ids(client)
        fallback_needed = fill_missing_with_installer and any(
            role not in configured for role in ("partner", "admin", "creator")
        )
        requested = _values_to_apply(
            supplied,
            configured,
            fill_missing_with_installer=fill_missing_with_installer,
            installer_id=installer_id,
        )
        if fallback_needed and installer_id not in active_ids:
            raise SystemExit("The Bitrix24 integration installer is not an active user")
        invalid = [role for role, value in requested.items() if value not in active_ids]
        invalid_auditors = [user_id for user_id in (auditor_ids or []) if user_id not in active_ids]
        if invalid or invalid_auditors:
            raise SystemExit("Configured Bitrix24 user IDs must belong to active users")
        update_event_bound = await _event_is_bound(client, TASK_UPDATE_EVENT)
        add_event_bound = await _event_is_bound(client, TASK_ADD_EVENT)
        if apply:
            await _save_ids(requested, auditor_ids=auditor_ids)
            if not update_event_bound:
                await client.call("event.bind", {"event": TASK_UPDATE_EVENT, "handler": TASK_EVENT_HANDLER})
                update_event_bound = await _event_is_bound(client, TASK_UPDATE_EVENT)
            if not add_event_bound:
                await client.call("event.bind", {"event": TASK_ADD_EVENT, "handler": TASK_EVENT_HANDLER})
                add_event_bound = await _event_is_bound(client, TASK_ADD_EVENT)

    if apply and not update_event_bound:
        raise SystemExit("Bitrix24 task update event could not be verified")
    if apply and not add_event_bound:
        raise SystemExit("Bitrix24 task add event could not be verified")

    configured = await _configured_ids()
    configured_auditor_ids = await _configured_auditor_ids()
    configured_users = list(configured.values()) + configured_auditor_ids
    valid = sum(value in active_ids for value in configured_users)
    print(f"task_responsible_roles_configured={sum(role in configured for role in ('partner', 'admin'))}")
    print(f"task_auditors_configured={len(configured_auditor_ids)}")
    print(f"task_configured_users_valid={valid}/{len(configured_users)}")
    print(f"task_update_event={'bound' if update_event_bound else 'missing'}")
    print(f"task_add_event={'bound' if add_event_bound else 'missing'}")


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
            auditor_ids=args.auditor_ids,
            fill_missing_with_installer=args.fill_missing_with_installer,
        )
    )


if __name__ == "__main__":
    main()
