from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.schemas.training import (
    FAQRead,
    ImportantNoteRead,
    InstructionRead,
    TrainingVideoRead,
)
from app.services import training_service

router = APIRouter(prefix="/training", tags=["training"])


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
