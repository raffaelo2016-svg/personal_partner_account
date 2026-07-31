"""Run the read-only Bitrix24 stage-1 survey.

Usage: poetry run python -m app.integrations.bitrix24.survey_cli --output ../docs/bitrix24/survey-result.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import settings
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.survey import Bitrix24Survey


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Bitrix24 technical survey")
    parser.add_argument("--output", type=Path, required=True, help="Path for the sanitized JSON report")
    return parser.parse_args()


async def _run(output: Path) -> None:
    if not settings.BITRIX_CLIENT_ENDPOINT or not settings.BITRIX_ACCESS_TOKEN:
        raise SystemExit("Set BITRIX_CLIENT_ENDPOINT and BITRIX_ACCESS_TOKEN in backend/.env")

    async with Bitrix24Client(settings.BITRIX_CLIENT_ENDPOINT, settings.BITRIX_ACCESS_TOKEN) as client:
        survey = Bitrix24Survey(
            client,
            smart_process_entity_type_id=settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
            deal_category_id=settings.BITRIX_DEAL_CATEGORY_ID,
        )
        result = await survey.run()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sanitized survey saved to {output}")


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.output))


if __name__ == "__main__":
    main()
