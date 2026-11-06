"""Atomic, repeat-safe import of the three approved FNS clients at zero tariff.

Default: rehearse and roll back. --apply: rehearse, commit, verify independently.
"""

import argparse
import ast
import subprocess
from pathlib import Path

PARTNER_ID = "29bd57c9-ee2d-4165-b75e-f71fdf217524"
IMPORT_ID = "fns-october-2026-approved-three-v1"
ROWS = [
    {"source_row": 27, "full_name": "Кучеренко Яна Владимировна", "case_number": "А54-7601/2025",
     "region": "Рязанская область"},
    {"source_row": 28, "full_name": "РЕШЕТНИКОВ ВЯЧЕСЛАВ СЕРГЕЕВИЧ", "case_number": "А19-25572/2025",
     "region": "Иркутская область"},
    {"source_row": 29, "full_name": "МАСЛОВ ПЁТР АЛЕКСАНДРОВИЧ", "case_number": "А70-24270/2025",
     "region": "Тюменская область"},
]

WORKER = r'''
import asyncio
import re
from uuid import UUID, uuid5

from sqlalchemy import select
from app.database import async_session
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.partner import Partner
from app.models.user import User
from app.integrations.bitrix24.clients import schedule_client_creation

def normalize(value):
    return re.sub(r"[^а-яa-z0-9]", "", str(value or "").casefold().replace("ё", "е").replace("a", "а"))

def metadata(client):
    return (client.document_generation_data or {}).get("source_import", {})

async def verify(session, clients):
    if len(clients) != 3:
        raise RuntimeError("Expected exactly three approved clients")
    for row in ROWS:
        matches = [c for c in clients if normalize(c.case_number) == normalize(row["case_number"])]
        if len(matches) != 1:
            raise RuntimeError("Missing or duplicate case: " + row["case_number"])
        c = matches[0]
        if (c.partner_id != UUID(PARTNER_ID) or c.deleted_at is not None or
            c.full_name != row["full_name"] or c.region != row["region"] or
            c.court_procedure_date is not None or metadata(c).get("import_id") != IMPORT_ID):
            raise RuntimeError("Client verification failed: " + row["full_name"])
        fee = await session.scalar(select(CourtFee.id).where(
            CourtFee.client_id == c.id, CourtFee.deleted_at.is_(None)
        ).limit(1))
        if fee is not None:
            raise RuntimeError("No fee record should be created for this zero-tariff import")
        print("CLIENT_OK", c.full_name, c.case_number, c.region, "id=" + str(c.id), flush=True)

async def main():
    async with async_session() as session:
        try:
            partner = await session.scalar(select(Partner).where(
                Partner.id == UUID(PARTNER_ID), Partner.deleted_at.is_(None)
            ).with_for_update())
            if (partner is None or partner.status != "active" or
                normalize(partner.company_name) != normalize("Федеральная Налоговая Служба")):
                raise RuntimeError("Approved FNS partner was not found")
            user = await session.get(User, partner.user_id)
            if user is None or user.email.casefold() != "sweet_86@vk.com":
                raise RuntimeError("FNS account differs from the reviewed card")
            if partner.court_fee_per_client != 0:
                raise RuntimeError("FNS tariff changed; refusing to import with different terms")

            all_clients = list((await session.scalars(select(Client))).all())
            existing = {}
            for row in ROWS:
                matches = [c for c in all_clients if
                    normalize(c.full_name) == normalize(row["full_name"]) or
                    normalize(c.case_number) == normalize(row["case_number"])]
                if matches:
                    if len(matches) != 1:
                        raise RuntimeError("Several existing matches: " + row["full_name"])
                    c = matches[0]
                    if (c.partner_id != partner.id or c.deleted_at is not None or
                        normalize(c.full_name) != normalize(row["full_name"]) or
                        normalize(c.case_number) != normalize(row["case_number"]) or
                        metadata(c).get("import_id") != IMPORT_ID):
                        raise RuntimeError("Existing client needs manual review: " + row["full_name"])
                    existing[row["case_number"]] = c

            created = []
            for row in ROWS:
                if row["case_number"] in existing:
                    continue
                c = Client(
                    id=uuid5(partner.id, IMPORT_ID + ":" + row["case_number"]),
                    partner_id=partner.id, type="in_court",
                    # Filed cases, consistent with the existing FNS import workflow.
                    # No bankruptcy procedure or hearing outcome is inferred.
                    status="sent_to_court", document_preparation_mode="uritech",
                    full_name=row["full_name"], case_number=row["case_number"], region=row["region"],
                    court_procedure_date=None,
                    document_generation_data={"source_import": {
                        "import_id": IMPORT_ID, "source_filename": "октябрь новые люди (1).xlsx",
                        "source_sheet": "Лист1", "source_row": row["source_row"],
                        "source_partner": "ИФНС", "original_status": None,
                        "hearing_date": None, "tariff_rub": 0,
                    }},
                )
                session.add(c)
                await session.flush()
                # Do not use create_court_fee_for_client: legacy code replaces a zero
                # tariff with 15000 RUB through `value or default`.
                await schedule_client_creation(session, c, partner=partner)
                await session.refresh(c)
                created.append(c)
                session.add(AuditLog(
                    action="import_client", target_type="client", target_id=str(c.id),
                    details={"import_id": IMPORT_ID, "partner_id": PARTNER_ID,
                             "source_row": row["source_row"], "tariff_rub": 0},
                ))
            await session.flush()
            await verify(session, list(existing.values()) + created)
            print("SUMMARY created=" + str(len(created)), "already_imported=" + str(len(existing)),
                  "approved_clients=3 new_charges_rub=0", flush=True)
            if APPLY:
                await session.commit()
            else:
                await session.rollback()
                print("DRY_RUN_OK: no changes saved", flush=True)
                return
        except BaseException:
            await session.rollback()
            raise
    async with async_session() as session:
        saved = list((await session.scalars(select(Client).where(
            Client.partner_id == UUID(PARTNER_ID), Client.deleted_at.is_(None)
        ))).all())
        await verify(session, [c for c in saved if metadata(c).get("import_id") == IMPORT_ID])
        print("FNS_CLIENT_COUNT=" + str(len(saved)), flush=True)
    print("IMPORT_OK: three FNS clients saved and verified; no charges or procedure dates added", flush=True)

asyncio.run(main())
'''


def validate_rows(rows):
    if len(rows) != 3:
        raise ValueError("Expected three approved rows")
    for key in ("full_name", "case_number", "source_row"):
        if len({r[key] for r in rows}) != 3:
            raise ValueError("Missing or duplicate " + key)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--app-dir", type=Path, default=Path("/srv/personal_partner_account"))
    args = parser.parse_args()
    validate_rows(ROWS)
    for apply in ([False, True] if args.apply else [False]):
        code = ("ROWS=" + repr(ROWS) + "\nPARTNER_ID=" + repr(PARTNER_ID) +
                "\nIMPORT_ID=" + repr(IMPORT_ID) + "\nAPPLY=" + repr(apply) + "\n" + WORKER)
        ast.parse(code)
        subprocess.run(
            ["docker", "compose", "-f", "docker-compose.prod.yml", "exec", "-T", "backend", "python", "-"],
            input=code, text=True, cwd=args.app_dir, check=True,
        )


if __name__ == "__main__":
    main()
