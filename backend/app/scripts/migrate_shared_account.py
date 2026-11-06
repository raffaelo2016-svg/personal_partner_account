"""Миграция с общей учётной записи администратора на персональные.

Что делает команда:
  1. находит общую (устаревшую) учётную запись администратора;
  2. создаёт приглашения на указанные почты;
  3. отключает общую учётку, сохраняя её для истории.

Примеры:
    # только отключить общую учётку
    python -m app.scripts.migrate_shared_account --email admin@uritech.ru

    # создать приглашения и отключить общую учётку
    python -m app.scripts.migrate_shared_account \
        --email admin@uritech.ru \
        --invite a.ivanov@uritech.ru b.petrova@uritech.ru

    # список почт из файла (по одной в строке)
    python -m app.scripts.migrate_shared_account --invite-file admins.txt

    # посмотреть план без изменений
    python -m app.scripts.migrate_shared_account --invite-file admins.txt --dry-run
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.user import User
from app.services import admin_access_service as access
from app.services.email_service import send_invite_email


def _read_emails(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    emails: list[str] = []
    for line in text.replace(";", ",").splitlines():
        for chunk in line.split(","):
            value = chunk.strip().strip('"')
            if "@" in value:
                emails.append(value)
    return emails


async def _run(args: argparse.Namespace) -> int:
    emails = list(args.invite or [])
    if args.invite_file:
        emails.extend(_read_emails(args.invite_file))
    emails = list(dict.fromkeys(access.normalize_email(e) for e in emails if e.strip()))

    async with async_session() as session:
        shared = await access.find_shared_admin(session, args.email)
        if shared is None:
            print("Общая учётная запись не найдена. Укажите её через --email.")
            return 1

        actor_row = await session.execute(
            select(User)
            .where(User.role == "super_admin", User.is_active.is_(True))
            .order_by(User.created_at)
            .limit(1)
        )
        actor = actor_row.scalar_one_or_none()

        print(f"Общая учётная запись: {shared.email} (id={shared.id})")
        print(f"Приглашений к созданию: {len(emails)}")
        if emails:
            print(f"Роль в приглашениях: {args.role}, срок: {args.ttl} ч")
        if actor is None:
            print("Не найден активный супер-администратор: сначала создайте его через /setup.")
            return 1

        if args.dry_run:
            print("Режим проверки: изменения не применяются.")
            for email in emails:
                print(f"  + приглашение для {email}")
            print(f"  - отключение общей учётки {shared.email}")
            return 0

        created, failed = await access.bulk_invite(
            session,
            emails=emails,
            role=args.role,
            actor=actor,
            ttl_hours=args.ttl,
        )
        await access.disable_shared_admin(session, shared, actor_label="migration-cli")
        await session.commit()

        print()
        for invite, token in created:
            url = access.invite_url(token)
            delivered = await send_invite_email(
                invite.email,
                url,
                access.ROLE_LABELS.get(invite.role, invite.role),
                actor.email,
                invite.expires_at.strftime("%d.%m.%Y %H:%M"),
            )
            status = "письмо отправлено" if delivered else "письмо не настроено — передайте ссылку вручную"
            print(f"  + {invite.email}: {url}  [{status}]")

        for email, reason in failed:
            print(f"  ! {email}: {reason}")

        print()
        print(f"Общая учётная запись {shared.email} отключена и помечена как устаревшая.")
        print(f"Приглашений создано: {len(created)}, ошибок: {len(failed)}.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Миграция с общей учётной записи администратора")
    parser.add_argument("--email", help="почта общей учётной записи (иначе ищется автоматически)")
    parser.add_argument("--invite", nargs="*", help="почты для приглашений")
    parser.add_argument("--invite-file", help="файл со списком почт")
    parser.add_argument("--role", default="admin", choices=["admin", "super_admin"])
    parser.add_argument("--ttl", type=int, default=72, choices=[24, 72, 168])
    parser.add_argument("--dry-run", action="store_true", help="только показать план")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
