"""Очистка журнала доступа: удаляет записи старше срока хранения.

По ТЗ журнал хранится 12 месяцев. Запускать по расписанию (cron/systemd timer):

    python -m app.scripts.cleanup_audit --days 365
    python -m app.scripts.cleanup_audit --days 365 --dry-run
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.database import async_session
from app.models.audit_log import AuditLog


async def _run(days: int, dry_run: bool) -> int:
    threshold = datetime.now(UTC) - timedelta(days=days)
    async with async_session() as session:
        count = (
            await session.execute(select(func.count(AuditLog.id)).where(AuditLog.created_at < threshold))
        ).scalar_one()

        print(f"Записей старше {days} дней ({threshold:%d.%m.%Y}): {count}")
        if dry_run:
            print("Режим проверки: удаление не выполняется.")
            return 0

        if count:
            await session.execute(delete(AuditLog).where(AuditLog.created_at < threshold))
            await session.commit()
            print(f"Удалено записей: {count}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Очистка журнала доступа")
    parser.add_argument("--days", type=int, default=365, help="срок хранения в днях")
    parser.add_argument("--dry-run", action="store_true", help="только посчитать")
    args = parser.parse_args()
    return asyncio.run(_run(args.days, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
