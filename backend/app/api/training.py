from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.schemas.training import (
    FAQRead,
    ImportantNoteRead,
    InstructionRead,
    TrainingProgressRead,
    TrainingVideoRead,
)
from app.services import training_service

router = APIRouter(prefix="/training", tags=["training"])

# Ключ урока — короткий латинский слаг из содержания курса («intro», «finance»).
LessonKey = Path(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")


@router.get("/videos", response_model=list[TrainingVideoRead])
async def get_videos(
    _current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await training_service.list_videos(db)


@router.get("/faq", response_model=list[FAQRead])
async def get_faq(
    _current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await training_service.list_faqs(db)


@router.get("/instructions", response_model=list[InstructionRead])
async def get_instructions(
    _current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await training_service.list_instructions(db)


@router.get("/important", response_model=list[ImportantNoteRead])
async def get_important(
    _current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await training_service.list_important_notes(db)


@router.get("/progress", response_model=TrainingProgressRead)
async def get_progress(
    current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    completed = await training_service.list_completed_lessons(db, current_user.id)
    return TrainingProgressRead(completed=completed)


@router.put("/progress/{lesson_key}", response_model=TrainingProgressRead)
async def complete_lesson(
    lesson_key: str = LessonKey,  # noqa: B008
    current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await training_service.complete_lesson(db, current_user.id, lesson_key)
    completed = await training_service.list_completed_lessons(db, current_user.id)
    return TrainingProgressRead(completed=completed)


@router.delete("/progress/{lesson_key}", response_model=TrainingProgressRead)
async def reset_lesson(
    lesson_key: str = LessonKey,  # noqa: B008
    current_user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    await training_service.reset_lesson(db, current_user.id, lesson_key)
    completed = await training_service.list_completed_lessons(db, current_user.id)
    return TrainingProgressRead(completed=completed)
