from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.models.news import NewsPost, NewsReceipt
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/news", tags=["news"])
admin_router = APIRouter(prefix="/admin/news", tags=["admin-news"])


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
        select(func.count()).select_from(NewsReceipt)
        .where(NewsReceipt.post_id == post_id, NewsReceipt.read_at.is_not(None))
    )
    acknowledged = await db.scalar(
        select(func.count()).select_from(NewsReceipt)
        .where(NewsReceipt.post_id == post_id, NewsReceipt.acknowledged_at.is_not(None))
    )
    return {"total": total or 0, "read": read or 0, "acknowledged": acknowledged or 0}
