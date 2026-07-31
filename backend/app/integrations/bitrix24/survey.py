from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error

REQUIRED_METHODS = (
    "app.info",
    "event.bind",
    "crm.item.fields",
    "crm.item.add",
    "crm.item.update",
    "crm.category.list",
    "crm.status.list",
    "user.get",
    "disk.storage.getlist",
    "disk.folder.uploadfile",
    "im.chat.add",
    "tasks.task.add",
    "tasks.task.update",
    "sonet_group.create",
    "sonet_group.get",
)


class Bitrix24Survey:
    """Read-only technical survey of the connected Bitrix24 portal."""

    def __init__(self, client: Bitrix24Client, *, smart_process_entity_type_id: int, deal_category_id: int) -> None:
        self.client = client
        self.smart_process_entity_type_id = smart_process_entity_type_id
        self.deal_category_id = deal_category_id

    async def _safe_call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return {"ok": True, "result": await self.client.call(method, params)}
        except Bitrix24Error as exc:
            return {
                "ok": False,
                "error": {"code": exc.code, "description": exc.description, "status_code": exc.status_code},
            }

    async def _safe_list(
        self, method: str, params: dict[str, Any] | None = None, *, result_key: str | None = None
    ) -> dict[str, Any]:
        try:
            result = await self.client.list_all(method, params, result_key=result_key)
            return {"ok": True, "result": result}
        except Bitrix24Error as exc:
            return {
                "ok": False,
                "error": {"code": exc.code, "description": exc.description, "status_code": exc.status_code},
            }

    async def run(self) -> dict[str, Any]:
        availability: dict[str, Any] = {}
        for method in REQUIRED_METHODS:
            availability[method] = await self._safe_call("method.get", {"name": method})

        users = await self._safe_list("user.get", {"FILTER": {"ACTIVE": True}})
        if users["ok"] and isinstance(users["result"], list):
            users["result"] = [
                {
                    key: row.get(key)
                    for key in ("ID", "ACTIVE", "NAME", "LAST_NAME", "WORK_POSITION")
                    if row.get(key) is not None
                }
                for row in users["result"]
            ]

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "read_only": True,
            "oauth_refresh_verified": False,
            "oauth_refresh_note": "Requires persistent encrypted token storage before rotating refresh_token.",
            "targets": {
                "partner_smart_process_entity_type_id": self.smart_process_entity_type_id,
                "arbitration_deal_category_id": self.deal_category_id,
            },
            "app": await self._safe_call("app.info"),
            "scopes": await self._safe_call("scope"),
            "method_availability": availability,
            "crm": {
                "partner_fields": await self._safe_call(
                    "crm.item.fields",
                    {"entityTypeId": self.smart_process_entity_type_id, "useOriginalUfNames": "Y"},
                ),
                "contact_fields": await self._safe_call(
                    "crm.item.fields", {"entityTypeId": 3, "useOriginalUfNames": "Y"}
                ),
                "deal_fields": await self._safe_call("crm.item.fields", {"entityTypeId": 2, "useOriginalUfNames": "Y"}),
                "partner_categories": await self._safe_call(
                    "crm.category.list", {"entityTypeId": self.smart_process_entity_type_id}
                ),
                "deal_categories": await self._safe_call("crm.category.list", {"entityTypeId": 2}),
                "statuses": await self._safe_list("crm.status.list"),
            },
            "users": users,
            "disk_storages": await self._safe_list("disk.storage.getlist"),
        }
