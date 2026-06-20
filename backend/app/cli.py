"""Management-команды. Запуск: python -m app.cli <command>"""

import asyncio
import sys

import structlog
from sqlalchemy import select

from app.database import async_session
from app.models.partner import Partner
from app.services.chat_service import ensure_rooms_for_partner

logger = structlog.get_logger()


async def ensure_chat_rooms() -> None:
    """Создать недостающие чат-комнаты для всех партнёров."""
    async with async_session() as session:
        partners = (await session.execute(select(Partner).where(Partner.deleted_at.is_(None)))).scalars().all()
        for partner in partners:
            await ensure_rooms_for_partner(session, str(partner.id))
        await session.commit()
    logger.info("chat_rooms_ensured", partners_count=len(partners))


COMMANDS = {
    "ensure-chat-rooms": ensure_chat_rooms,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python -m app.cli <command>")
        print(f"Commands: {', '.join(COMMANDS)}")
        sys.exit(1)
    asyncio.run(COMMANDS[sys.argv[1]]())


if __name__ == "__main__":
    main()
