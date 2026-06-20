from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import FAQ, ImportantNote, Instruction, TrainingVideo


async def list_videos(db: AsyncSession) -> list[TrainingVideo]:
    result = await db.execute(select(TrainingVideo).order_by(TrainingVideo.order))
    return list(result.scalars().all())


async def list_faqs(db: AsyncSession) -> list[FAQ]:
    result = await db.execute(select(FAQ).order_by(FAQ.order))
    return list(result.scalars().all())


async def list_instructions(db: AsyncSession) -> list[Instruction]:
    result = await db.execute(select(Instruction).order_by(Instruction.order))
    return list(result.scalars().all())


async def list_important_notes(db: AsyncSession) -> list[ImportantNote]:
    result = await db.execute(select(ImportantNote).order_by(ImportantNote.order))
    return list(result.scalars().all())
