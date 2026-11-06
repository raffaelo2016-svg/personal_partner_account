"""Idempotent, atomic import of the approved 14 ProReshenia clients.

Run on the production host with --apply. Default mode validates and rolls back.
Only client records and their normal fees/Bitrix projections are created.
Hearing dates remain source metadata; court_procedure_date stays empty.
"""

import argparse
import ast
import subprocess
from pathlib import Path

ROWS = [{'source_row': 1, 'full_name': 'Синяков Алексей Владимирович', 'case_number': 'А41-28771/2025', 'region': 'Московская область', 'hearing_date': '2026-10-21'}, {'source_row': 2, 'full_name': 'Барсамян Николай Масисович', 'case_number': 'А41-78311/2024', 'region': 'Московская область', 'hearing_date': '2026-10-21'}, {'source_row': 3, 'full_name': 'Вавилов Артем Николаевич', 'case_number': 'А72-9190/2025', 'region': 'Ульяновская область', 'hearing_date': '2026-10-21'}, {'source_row': 4, 'full_name': 'Самохвалова Вера Владимировна', 'case_number': 'А41-6857/2025', 'region': 'Московская область', 'hearing_date': '2026-10-21'}, {'source_row': 5, 'full_name': 'Беляев Сергей Владимирович', 'case_number': 'А41-45107/2023', 'region': 'Московская область', 'hearing_date': '2026-10-21'}, {'source_row': 6, 'full_name': 'Тен Александра Валерьевна', 'case_number': 'А08-4574/2026', 'region': 'Белгородская область', 'hearing_date': '2026-10-10'}, {'source_row': 7, 'full_name': 'Голота Владимир Иванович', 'case_number': 'А08-3554/2023', 'region': 'Белгородская область', 'hearing_date': '2026-10-20'}, {'source_row': 8, 'full_name': 'Шмелев Сергей Борисович', 'case_number': 'А39-2000/2026', 'region': 'Республика Мордовия', 'hearing_date': '2026-10-20'}, {'source_row': 9, 'full_name': 'Вашков Александр Анатольевич', 'case_number': 'А52-2001/2024', 'region': 'Псковская область', 'hearing_date': '2026-10-19'}, {'source_row': 10, 'full_name': 'Хавов Александр Борисович', 'case_number': 'А27-7700/2024', 'region': 'Кемеровская область', 'hearing_date': '2026-11-09'}, {'source_row': 11, 'full_name': 'Боброва Татьяна Петровна', 'case_number': 'А71-21602/2023', 'region': 'Удмуртская область', 'hearing_date': '2026-11-16'}, {'source_row': 12, 'full_name': 'Неудахина Кристина Ивановна', 'case_number': 'А33-36022/2024', 'region': 'Красноярский край', 'hearing_date': '2026-10-17'}, {'source_row': 13, 'full_name': 'Авдыев Марат Александрович', 'case_number': 'А75-579/2025', 'region': 'Ханты-Мансийского АО', 'hearing_date': '2026-10-13'}, {'source_row': 14, 'full_name': 'Царева Мария Владимировна', 'case_number': 'А27-6525/2025', 'region': 'Кемеровская область', 'hearing_date': '2026-10-13'}]
PARTNER_ID = "12f75248-0afc-4d3c-b326-7f5d4a9ea685"
IMPORT_ID = "proreshenie-october-2026-approved-14-v1"

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
            if partner is None or partner.inn != "0274390698" or partner.status != "active":
                raise RuntimeError("Approved active partner was not found")
            user = await session.get(User, partner.user_id)
            if user is None or user.email.casefold() != "info@pro-reshenia.ru":
                raise RuntimeError("Partner email differs from the reviewed card")
            if partner.court_fee_per_client != 1000000 or partner.payment_term_days != 10:
                raise RuntimeError("Partner financial terms changed; review required")
            if partner.free_client_limit:
                raise RuntimeError("Promotion settings changed; review required")

            all_clients = list((await session.scalars(select(Client))).all())
            existing = {}
            for row in ROWS:
                matches = [c for c in all_clients if
                    normalize(c.case_number) == normalize(row["case_number"]) or
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
                    existing[row["case_number"]] = c

            # Keep audit rows in the same transaction as the import, including dry-run.
            def transaction_audit(action, **kwargs):
                session.add(AuditLog(action=action, **kwargs))
            finance_service.audit_log = transaction_audit

            created = []
            for row in ROWS:
                if row["case_number"] in existing:
                    continue
                c = Client(
                    id=uuid5(partner.id, IMPORT_ID + ":" + row["case_number"]),
                    partner_id=partner.id,
                    type="in_court",
                    # Workflow stage only; no realization/restructuring procedure is inferred.
                    status="waiting_hearing",
                    document_preparation_mode="uritech",
                    full_name=row["full_name"],
                    case_number=row["case_number"],
                    region=row["region"],
                    court_procedure_date=None,
                    document_generation_data={"source_import": {
                        "import_id": IMPORT_ID,
                        "source_filename": "октябрь новые люди (1).xlsx",
                        "source_sheet": "Лист1", "source_row": row["source_row"],
                        "original_status": "Рассмотрение дела",
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
            if len(imported) != 14:
                raise RuntimeError("Expected exactly 14 imported or previously imported clients")
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
            if total != 14000000:
                raise RuntimeError("Fee total differs from approved 140000 RUB")
            print("SUMMARY created=" + str(len(created)), "already_imported=" + str(len(existing)),
                  "total_clients=14 total_fees_rub=140000", "fee_due_dates=" + ",".join(sorted(deadlines)), flush=True)
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
        if len(saved) != 14 or any(c.court_procedure_date is not None for c in saved):
            raise RuntimeError("Post-commit verification failed")
        for row in ROWS:
            matches = [c for c in saved if c.case_number == row["case_number"]]
            if len(matches) != 1 or metadata(matches[0])["hearing_date"] != row["hearing_date"]:
                raise RuntimeError("Post-commit source verification failed")
    print("IMPORT_OK: 14 clients verified in ProReshenia; hearing dates preserved; no procedure dates assigned", flush=True)

asyncio.run(main())
'''


def validate_rows(rows):
    from datetime import date

    if len(rows) != 14:
        raise ValueError("Expected 14 approved source rows")
    for key in ("case_number", "full_name", "source_row"):
        if len({r[key] for r in rows}) != 14:
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
