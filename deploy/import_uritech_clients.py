"""Idempotent, atomic import of the four missing URITECH clients.

Run on the production host with --apply. Default mode validates and rolls back.
Only client records and their normal fees/Bitrix projections are created.
Hearing dates remain source metadata; court_procedure_date stays empty.
"""

import argparse
import ast
import subprocess
from pathlib import Path

ROWS = [{'source_row': 16, 'full_name': 'ЖУКОВ ЕГОР РОМАНОВИЧ', 'case_number': None, 'source_status': 'Документы отправлены', 'region': 'Санкт-Петербурга и Ленинградской области', 'hearing_date': '2026-10-08'}, {'source_row': 17, 'full_name': 'Антипов Андрей Дмитриевич', 'case_number': 'А54-9536/2026', 'source_status': 'Документы отправлены', 'region': 'Рязанская область', 'hearing_date': '2026-10-09'}, {'source_row': 18, 'full_name': 'Усольцева Ольга Владимировна', 'case_number': None, 'source_status': 'Документы отправлены', 'region': 'Ярославская область', 'hearing_date': '2026-10-09'}, {'source_row': 23, 'full_name': 'Романчук Татьяна Николаевна', 'case_number': None, 'source_status': 'Документ отправлены', 'region': 'Тюменская область', 'hearing_date': '2026-10-14'}]
PARTNER_ID = "493136d2-ce20-46a6-9e79-3ddd34201e44"
IMPORT_ID = "uritech-october-2026-missing-four-v1"

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
from app.services import finance_service

def normalize(value):
    value = str(value or "").casefold().replace("ё", "е").replace("a", "а")
    return re.sub(r"[^а-яa-z0-9]", "", value)

def metadata(client):
    return (client.document_generation_data or {}).get("source_import", {})

async def main():
    async with async_session() as session:
        try:
            partner = await session.scalar(select(Partner).where(
                Partner.id == UUID(PARTNER_ID), Partner.deleted_at.is_(None)
            ).with_for_update())
            if partner is None or partner.inn != "3100009570" or partner.status != "active":
                raise RuntimeError("Approved active partner was not found")
            user = await session.get(User, partner.user_id)
            if user is None or user.email.casefold() != "raffaelo2016@gmail.com":
                raise RuntimeError("Partner email differs from the reviewed card")
            if partner.court_fee_per_client != 1000000 or partner.payment_term_days != 14:
                raise RuntimeError("Partner financial terms changed; review required")
            if partner.free_client_limit:
                raise RuntimeError("Promotion settings changed; review required")

            all_clients = list((await session.scalars(select(Client))).all())
            existing = {}
            for row in ROWS:
                matches = [c for c in all_clients if
                    (row["case_number"] and normalize(c.case_number) == normalize(row["case_number"])) or
                    normalize(c.full_name) == normalize(row["full_name"])]
                if matches:
                    if len(matches) != 1:
                        raise RuntimeError("Several existing matches: " + row["full_name"])
                    c = matches[0]
                    if (c.partner_id != partner.id or c.deleted_at is not None or
                        normalize(c.case_number) != normalize(row["case_number"]) or
                        normalize(c.full_name) != normalize(row["full_name"]) or
                        metadata(c).get("import_id") != IMPORT_ID or
                        metadata(c).get("hearing_date") != row["hearing_date"]):
                        raise RuntimeError("Existing client requires manual review: " + row["full_name"])
                    existing[row["full_name"]] = c

            # Keep audit rows in the same transaction as the import, including dry-run.
            def transaction_audit(action, **kwargs):
                session.add(AuditLog(action=action, **kwargs))
            finance_service.audit_log = transaction_audit

            created = []
            for row in ROWS:
                if row["full_name"] in existing:
                    continue
                c = Client(
                    id=uuid5(partner.id, IMPORT_ID + ":" + row["full_name"]),
                    partner_id=partner.id,
                    type="in_court" if row["case_number"] else "before_court",
                    # Workflow stage only; no realization/restructuring procedure is inferred.
                    status="sent_to_court",
                    document_preparation_mode="uritech",
                    full_name=row["full_name"],
                    case_number=row["case_number"],
                    region=row["region"],
                    court_procedure_date=None,
                    document_generation_data={"source_import": {
                        "import_id": IMPORT_ID,
                        "source_filename": "октябрь новые люди (1).xlsx",
                        "source_sheet": "Лист1", "source_row": row["source_row"],
                        "original_status": row["source_status"],
                        "original_region": row["region"],
                        "hearing_date": row["hearing_date"],
                        "hearing_date_meaning": "Дата судебного заседания, подтверждено пользователем",
                    }},
                )
                session.add(c)
                await session.flush()
                await finance_service.create_court_fee_for_client(session, c, partner)
                await schedule_client_creation(session, c, partner=partner)
                await session.refresh(c)
                created.append(c)
                session.add(AuditLog(
                    action="import_client", target_type="client", target_id=str(c.id),
                    details={"import_id": IMPORT_ID, "source_row": row["source_row"],
                             "partner_id": PARTNER_ID, "hearing_date": row["hearing_date"]},
                ))

            await session.flush()
            imported = list(existing.values()) + created
            if len(imported) != 4:
                raise RuntimeError("Expected exactly 4 imported or previously imported clients")
            total = 0
            deadlines = set()
            for c in imported:
                if c.court_procedure_date is not None:
                    raise RuntimeError("Procedure date must remain empty: " + c.full_name)
                fees = list((await session.scalars(select(CourtFee).where(
                    CourtFee.client_id == c.id, CourtFee.deleted_at.is_(None)
                ))).all())
                if len(fees) != 1 or fees[0].amount != 1000000:
                    raise RuntimeError("Expected one standard 10000 RUB fee: " + c.full_name)
                total += fees[0].amount
                deadlines.add(fees[0].due_date.isoformat())
                print("CLIENT_OK", c.full_name, c.case_number,
                      "hearing=" + metadata(c)["hearing_date"], "id=" + str(c.id), flush=True)
            if total != 4000000:
                raise RuntimeError("Fee total differs from approved 40000 RUB")
            print("SUMMARY created=" + str(len(created)), "already_imported=" + str(len(existing)),
                  "total_clients=4 total_fees_rub=40000", "fee_due_dates=" + ",".join(sorted(deadlines)), flush=True)
            if APPLY:
                await session.commit()
            else:
                await session.rollback()
                print("DRY_RUN_OK: transaction rolled back; no clients created", flush=True)
                return
        except BaseException:
            await session.rollback()
            raise

    # Independent post-commit verification.
    async with async_session() as session:
        saved = list((await session.scalars(select(Client).where(
            Client.partner_id == UUID(PARTNER_ID), Client.deleted_at.is_(None)
        ))).all())
        saved = [c for c in saved if metadata(c).get("import_id") == IMPORT_ID]
        if len(saved) != 4 or any(c.court_procedure_date is not None for c in saved):
            raise RuntimeError("Post-commit verification failed")
        for row in ROWS:
            matches = [c for c in saved if c.full_name == row["full_name"]]
            if len(matches) != 1 or metadata(matches[0])["hearing_date"] != row["hearing_date"]:
                raise RuntimeError("Post-commit source verification failed")
    print("IMPORT_OK: four missing clients verified in URITECH; hearing dates preserved; no procedure dates assigned", flush=True)

asyncio.run(main())
'''


def validate_rows(rows):
    from datetime import date

    if len(rows) != 4:
        raise ValueError("Expected four approved source rows")
    for key in ("full_name", "source_row"):
        if len({r[key] for r in rows}) != 4:
            raise ValueError("Duplicate approved " + key)
    for row in rows:
        date.fromisoformat(row["hearing_date"])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--app-dir", type=Path, default=Path("/srv/personal_partner_account"))
    args = parser.parse_args()
    validate_rows(ROWS)
    # Always verify the full import in a rolled-back transaction before applying.
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
