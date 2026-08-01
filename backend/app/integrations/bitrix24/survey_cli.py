"""Run the read-only Bitrix24 stage-1 survey.

Usage: poetry run python -m app.integrations.bitrix24.survey_cli --output ../docs/bitrix24/survey-result.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.survey import Bitrix24Survey
from app.integrations.bitrix24.token_storage import decrypt_token
from app.models.bitrix_installation import BitrixInstallation


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Bitrix24 technical survey")
    parser.add_argument("--output", type=Path, required=True, help="Path for the sanitized JSON report")
    parser.add_argument(
        "--portal-domain",
        default=settings.BITRIX_ALLOWED_DOMAIN,
        help="Installed Bitrix24 portal whose encrypted access token should be used",
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Use BITRIX_CLIENT_ENDPOINT and BITRIX_ACCESS_TOKEN instead of encrypted storage",
    )
    return parser.parse_args()


async def _stored_credentials(db: AsyncSession, portal_domain: str) -> tuple[str, str]:
    installation = await db.scalar(
        select(BitrixInstallation).where(BitrixInstallation.portal_domain == portal_domain.strip().lower())
    )
    if installation is None:
        raise SystemExit(f"No encrypted Bitrix24 installation found for {portal_domain}")
    access_token = await decrypt_token(db, installation.access_token_encrypted)
    return installation.client_endpoint, access_token


async def _credentials(portal_domain: str, *, from_env: bool) -> tuple[str, str]:
    if from_env:
        if not settings.BITRIX_CLIENT_ENDPOINT or not settings.BITRIX_ACCESS_TOKEN:
            raise SystemExit("Set BITRIX_CLIENT_ENDPOINT and BITRIX_ACCESS_TOKEN in backend/.env")
        return settings.BITRIX_CLIENT_ENDPOINT, settings.BITRIX_ACCESS_TOKEN

    async with async_session() as db:
        return await _stored_credentials(db, portal_domain)


async def _run(output: Path, portal_domain: str, *, from_env: bool = False) -> None:
    client_endpoint, access_token = await _credentials(portal_domain, from_env=from_env)

    async with Bitrix24Client(client_endpoint, access_token) as client:
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
    asyncio.run(_run(args.output, args.portal_domain, from_env=args.from_env))


if __name__ == "__main__":
    main()
