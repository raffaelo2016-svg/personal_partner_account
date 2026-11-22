from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import (
    FAQ,
    ImportantNote,
    Instruction,
    TrainingLessonProgress,
    TrainingVideo,
)


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


async def list_completed_lessons(db: AsyncSession, user_id) -> list[str]:
    result = await db.execute(
        select(TrainingLessonProgress.lesson_key)
        .where(TrainingLessonProgress.user_id == user_id)
        .order_by(TrainingLessonProgress.completed_at, TrainingLessonProgress.lesson_key)
    )
    return list(result.scalars().all())


async def complete_lesson(db: AsyncSession, user_id, lesson_key: str) -> None:
    """Идемпотентно отмечает урок просмотренным."""
    statement = (
        insert(TrainingLessonProgress)
        .values(user_id=user_id, lesson_key=lesson_key)
        .on_conflict_do_nothing(index_elements=["user_id", "lesson_key"])
    )
    await db.execute(statement)
    await db.commit()


async def reset_lesson(db: AsyncSession, user_id, lesson_key: str) -> None:
    """Снимает отметку, если партнёр хочет пройти урок заново."""
    await db.execute(
        delete(TrainingLessonProgress).where(
            TrainingLessonProgress.user_id == user_id,
            TrainingLessonProgress.lesson_key == lesson_key,
        )
    )
    await db.commit()
