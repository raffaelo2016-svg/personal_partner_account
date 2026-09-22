import uuid
from datetime import UTC, datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.news import NewsPost, NewsReceipt
from app.models.notification import Notification
from app.models.user import User
from app.services.s3_service import delete_file_async, get_presigned_url, upload_file_async
from app.validation.files import file_extension, has_valid_signature

router = APIRouter(prefix="/news", tags=["news"])
admin_router = APIRouter(prefix="/admin/news", tags=["admin-news"])
logger = structlog.get_logger()

MAX_NEWS_IMAGE_BYTES = 5 * 1024 * 1024
NEWS_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def valid_news_image(data: bytes, extension: str) -> bool:
    if extension == ".webp":
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return has_valid_signature(data, extension)


class NewsInput(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    body: str = Field(min_length=1, max_length=20000)
    category: Literal["announcement", "update", "instruction"] = "announcement"
    important: bool = False
    pinned: bool = False
    requires_acknowledgement: bool = False


class NewsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    category: Literal["announcement", "update", "instruction"] | None = None
    important: bool | None = None
    pinned: bool | None = None
    requires_acknowledgement: bool | None = None


def serialize(post: NewsPost, receipt: NewsReceipt | None = None) -> dict:
    return {
        "id": str(post.id),
        "title": post.title,
        "body": post.body,
        "image_url": get_presigned_url(post.image_s3_key, expires_in=3600) if post.image_s3_key else None,
        "category": post.category,
        "important": post.important,
        "pinned": post.pinned,
        "requires_acknowledgement": post.requires_acknowledgement,
        "status": post.status,
        "published_at": post.published_at,
        "created_at": post.created_at,
        "read_at": receipt.read_at if receipt else None,
        "acknowledged_at": receipt.acknowledged_at if receipt else None,
    }


async def visible_post(db: AsyncSession, post_id: uuid.UUID) -> NewsPost:
    post = await db.get(NewsPost, post_id)
    if not post or post.status != "published":
        raise HTTPException(404, "News not found")
    return post


@router.get("")
async def list_news(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: User = Depends(require_role("partner")),  # noqa: B008
):
    rows = await db.execute(
        select(NewsPost, NewsReceipt)
        .outerjoin(NewsReceipt, (NewsReceipt.post_id == NewsPost.id) & (NewsReceipt.user_id == user.id))
        .where(NewsPost.status == "published")
        .order_by(NewsPost.pinned.desc(), NewsPost.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    total = await db.scalar(select(func.count()).select_from(NewsPost).where(NewsPost.status == "published"))
    return {"items": [serialize(post, receipt) for post, receipt in rows.all()], "total": total or 0}


@router.get("/unread-count")
async def unread_news_count(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: User = Depends(require_role("partner")),  # noqa: B008
):
    count = await db.scalar(
        select(func.count())
        .select_from(NewsPost)
        .outerjoin(NewsReceipt, (NewsReceipt.post_id == NewsPost.id) & (NewsReceipt.user_id == user.id))
        .where(NewsPost.status == "published", NewsReceipt.read_at.is_(None))
    )
    return {"count": count or 0}


@router.get("/{post_id}")
async def get_news(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: User = Depends(require_role("partner")),  # noqa: B008
):
    post = await visible_post(db, post_id)
    receipt = await db.get(NewsReceipt, (post.id, user.id))
    return serialize(post, receipt)


@router.put("/{post_id}/read")
async def read_news(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: User = Depends(require_role("partner")),  # noqa: B008
):
    post = await visible_post(db, post_id)
    receipt = await db.get(NewsReceipt, (post.id, user.id))
    if receipt is None:
        receipt = NewsReceipt(post_id=post.id, user_id=user.id)
        db.add(receipt)
    if receipt.read_at is None:
        receipt.read_at = datetime.now(UTC)
    await db.commit()
    return serialize(post, receipt)


@router.put("/{post_id}/acknowledge")
async def acknowledge_news(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: User = Depends(require_role("partner")),  # noqa: B008
):
    post = await visible_post(db, post_id)
    if not post.requires_acknowledgement:
        raise HTTPException(400, "Acknowledgement not required")
    receipt = await db.get(NewsReceipt, (post.id, user.id))
    if receipt is None:
        receipt = NewsReceipt(post_id=post.id, user_id=user.id)
        db.add(receipt)
    now = datetime.now(UTC)
    receipt.read_at = receipt.read_at or now
    receipt.acknowledged_at = receipt.acknowledged_at or now
    await db.commit()
    return serialize(post, receipt)


@admin_router.get("")
async def admin_list_news(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    posts = (await db.scalars(select(NewsPost).order_by(NewsPost.created_at.desc()).limit(200))).all()
    return {"items": [serialize(post) for post in posts]}


@admin_router.post("", status_code=201)
async def create_news(
    data: NewsInput,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: User = Depends(require_role("admin")),  # noqa: B008
):
    post = NewsPost(author_id=user.id, **data.model_dump())
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return serialize(post)


@admin_router.patch("/{post_id}")
async def update_news(
    post_id: uuid.UUID,
    data: NewsUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    post = await db.get(NewsPost, post_id)
    if not post or post.status == "archived":
        raise HTTPException(404, "News not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    await db.commit()
    await db.refresh(post)
    return serialize(post)


@admin_router.post("/{post_id}/image")
@limiter.limit("10/minute")
async def upload_news_image(
    request: Request,
    post_id: uuid.UUID,
    file: UploadFile = File(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    post = await db.get(NewsPost, post_id)
    if not post or post.status == "archived":
        raise HTTPException(404, "News not found")

    extension = file_extension(file.filename or "")
    content_type = file.content_type or ""
    if NEWS_IMAGE_MIME.get(extension) != content_type:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image")

    data = await file.read(MAX_NEWS_IMAGE_BYTES + 1)
    if len(data) > MAX_NEWS_IMAGE_BYTES:
        raise HTTPException(413, "Image must be 5 MB or smaller")
    if not valid_news_image(data, extension):
        raise HTTPException(415, "Invalid image content")

    new_key = await upload_file_async(data, f"news-cover{extension}", content_type)
    old_key = post.image_s3_key
    post.image_s3_key = new_key
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_file_async(new_key)
        raise
    await db.refresh(post)
    if old_key:
        try:
            await delete_file_async(old_key)
        except Exception:
            logger.warning("news_image_cleanup_failed", post_id=str(post.id))
    return serialize(post)


@admin_router.delete("/{post_id}/image")
async def delete_news_image(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    post = await db.get(NewsPost, post_id)
    if not post or post.status == "archived":
        raise HTTPException(404, "News not found")
    old_key = post.image_s3_key
    if old_key:
        post.image_s3_key = None
        await db.commit()
        await db.refresh(post)
        try:
            await delete_file_async(old_key)
        except Exception:
            logger.warning("news_image_cleanup_failed", post_id=str(post.id))
    return serialize(post)


@admin_router.post("/{post_id}/publish")
async def publish_news(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    post = await db.get(NewsPost, post_id)
    if not post or post.status == "archived":
        raise HTTPException(404, "News not found")
    if post.status != "published":
        post.status = "published"
        post.published_at = datetime.now(UTC)
        partner_ids = (await db.scalars(select(User.id).where(User.role == "partner", User.is_active.is_(True)))).all()
        db.add_all(
            Notification(
                user_id=user_id,
                type="news",
                title=post.title,
                message=post.body[:240],
                link=f"/dashboard/news/{post.id}",
            )
            for user_id in partner_ids
        )
    await db.commit()
    await db.refresh(post)
    return serialize(post)


@admin_router.post("/{post_id}/archive")
async def archive_news(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    post = await db.get(NewsPost, post_id)
    if not post:
        raise HTTPException(404, "News not found")
    post.status = "archived"
    await db.commit()
    return serialize(post)


@admin_router.get("/{post_id}/stats")
async def news_stats(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin")),  # noqa: B008
):
    if not await db.get(NewsPost, post_id):
        raise HTTPException(404, "News not found")
    total = await db.scalar(
        select(func.count()).select_from(User).where(User.role == "partner", User.is_active.is_(True))
    )
    read = await db.scalar(
        select(func.count())
        .select_from(NewsReceipt)
        .where(NewsReceipt.post_id == post_id, NewsReceipt.read_at.is_not(None))
    )
    acknowledged = await db.scalar(
        select(func.count())
        .select_from(NewsReceipt)
        .where(NewsReceipt.post_id == post_id, NewsReceipt.acknowledged_at.is_not(None))
    )
    return {"total": total or 0, "read": read or 0, "acknowledged": acknowledged or 0}
