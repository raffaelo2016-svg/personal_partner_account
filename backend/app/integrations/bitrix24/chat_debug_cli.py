from __future__ import annotations

import asyncio
import json
from typing import Any

from app.database import async_session
from app.integrations.bitrix24.chat import _event_file, _installation_token, normalize_dialog_id
from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error
from app.integrations.bitrix24.partners import active_installation


def _file_summary(value: Any) -> Any:
    if isinstance(value, list):
        return [_file_summary(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): (
                {
                    field: item.get(field)
                    for field in ("id", "fileId", "name", "size", "type", "extension", "mimeType")
                    if item.get(field) is not None
                }
                if isinstance(item, dict)
                else type(item).__name__
            )
            for key, item in value.items()
        }
    return type(value).__name__ if value is not None else None


def _event_summary(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {"event_type": type(event).__name__}
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    parsed_file = _event_file(data)
    return {
        "type": event.get("type"),
        "event_id": event.get("eventId"),
        "message_id": message.get("id"),
        "chat_id": message.get("chatId"),
        "author_id": message.get("authorId"),
        "text_length": len(str(message.get("text") or "")),
        "data_keys": sorted(data),
        "message_keys": sorted(message),
        "param_keys": sorted(params),
        "event_files": _file_summary(
            data.get("files") or message.get("files") or params.get("files") or params.get("FILES")
        ),
        "parsed_file": _file_summary(parsed_file),
    }


async def main() -> None:
    async with async_session() as db:
        installation = await active_installation(db)
        if installation is None or installation.im_bot_id is None:
            raise RuntimeError("Active Bitrix installation with bot is required")
        token = await _installation_token(db, installation)
        async with Bitrix24Client(installation.client_endpoint, token) as client:
            params: dict[str, Any] = {"botId": installation.im_bot_id, "limit": 20}
            if installation.im_bot_event_offset is not None:
                params["offset"] = installation.im_bot_event_offset
            queue = await client.call("imbot.v2.Event.get", params)
            events = queue.get("events", []) if isinstance(queue, dict) else []
            history = await client.call(
                "im.dialog.messages.get",
                {"DIALOG_ID": normalize_dialog_id("24522"), "LIMIT": 20},
            )

            report: dict[str, Any] = {
                "saved_offset": installation.im_bot_event_offset,
                "queue_type": type(queue).__name__,
                "next_offset": queue.get("nextOffset") if isinstance(queue, dict) else None,
                "events": [_event_summary(event) for event in events],
                "history_type": type(history).__name__,
            }
            if isinstance(history, dict):
                messages = history.get("messages")
                report["history_keys"] = sorted(history)
                report["history_messages"] = [
                    {
                        "id": item.get("id"),
                        "text_length": len(str(item.get("text") or "")),
                        "keys": sorted(item),
                        "params": _file_summary(item.get("params")),
                    }
                    for item in messages or []
                    if isinstance(item, dict)
                ]
                report["history_files"] = _file_summary(history.get("files"))

            file_data = next(
                (
                    _event_file(event.get("data"))
                    for event in reversed(events)
                    if isinstance(event, dict) and isinstance(event.get("data"), dict) and _event_file(event["data"])
                ),
                None,
            )
            if isinstance(file_data, dict):
                file_id = file_data.get("id") or file_data.get("fileId")
                try:
                    download = await client.call(
                        "imbot.v2.File.download",
                        {"botId": installation.im_bot_id, "fileId": file_id},
                    )
                    report["download_result_keys"] = (
                        sorted(download) if isinstance(download, dict) else type(download).__name__
                    )
                except Bitrix24Error as exc:
                    report["download_error"] = {"code": exc.code, "status_code": exc.status_code}

            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
