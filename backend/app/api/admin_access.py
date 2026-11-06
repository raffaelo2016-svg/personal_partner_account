from datetime import datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.invite import Invite
from app.models.user import User
from app.schemas.admin_access import (
    AdminRead,
    AdminUpdate,
    AuditEntry,
    AuditPage,
    BootstrapRequest,
    InviteCreate,
    InviteRead,
    MessageResponse,
    SetupStatus,
)
from app.services import admin_access_service as access
from app.services.email_service import send_invite_email
from app.services.password_reset_service import deliver_password_reset, request_password_reset

logger = structlog.get_logger()

router = APIRouter(tags=["admin-access"])


def _meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, (ua[:512] if ua else None)


def _admin_read(user: User) -> AdminRead:
    return AdminRead(
        id=str(user.id),
        email=user.email,
        login=user.login,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        is_legacy_shared=user.is_legacy_shared,
    )


async def _invite_reads(session: AsyncSession, invites: list[Invite]) -> list[InviteRead]:
    author_ids = {i.created_by for i in invites if i.created_by}
    authors: dict = {}
    if author_ids:
        rows = await session.execute(select(User).where(User.id.in_(author_ids)))
        authors = {u.id: u.email for u in rows.scalars().all()}

    reads = [
        InviteRead(
            id=str(i.id),
            email=i.email,
            role=i.role,
            status=i.status,
            expires_at=i.expires_at,
            created_at=i.created_at,
            created_by_label=authors.get(i.created_by),
        )
        for i in invites
    ]

    # Действующая ссылка доступна и после закрытия окна создания приглашения.
    for item in reads:
        if item.status == "active":
            token = await access.get_invite_token(item.id)
            if token:
                item.invite_url = access.invite_url(token)

    return reads


# ---------------------------------------------------------------- первичная настройка


@router.get("/setup/status", response_model=SetupStatus)
async def setup_status(db: AsyncSession = Depends(get_db)):  # noqa: B008
    return SetupStatus(needs_setup=await access.needs_setup(db))


@router.post("/setup/bootstrap", response_model=MessageResponse)
@limiter.limit("5/minute")
async def setup_bootstrap(
    request: Request,
    body: BootstrapRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    ip, ua = _meta(request)
    user = await access.consume_bootstrap_key(
        db,
        key=body.key,
        email=body.email,
        login=body.login,
        password=body.password,
        ip=ip,
        user_agent=ua,
    )
    await db.commit()
    logger.info("setup_bootstrap_ok", user_id=str(user.id))
    return MessageResponse(message="Супер-администратор создан. Войдите под своими данными.")


# ---------------------------------------------------------------- администраторы


@router.get("/admin/users", response_model=list[AdminRead])
async def list_admins(
    search: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("super_admin")),  # noqa: B008
):
    users = await access.list_admins(db, search=search)
    return [_admin_read(u) for u in users]


@router.patch("/admin/users/{user_id}", response_model=AdminRead)
async def update_admin(
    user_id: str,
    body: AdminUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("super_admin")),  # noqa: B008
):
    import uuid as _uuid

    try:
        target_id = _uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc

    ip, ua = _meta(request)
    target = await access.update_admin(
        db,
        target_id=target_id,
        actor=actor,
        role=body.role,
        is_active=body.is_active,
        ip=ip,
        user_agent=ua,
    )
    await db.commit()
    return _admin_read(target)


@router.post("/admin/users/{user_id}/reset-password", response_model=MessageResponse)
async def reset_admin_password(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("super_admin")),  # noqa: B008
):
    import uuid as _uuid

    try:
        target_id = _uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc

    target = await db.get(User, target_id)
    if target is None or target.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    delivery = await request_password_reset(db, target.email)
    if delivery:
        background_tasks.add_task(deliver_password_reset, delivery)
    return MessageResponse(message="Ссылка на сброс пароля отправлена на почту администратора.")


# ---------------------------------------------------------------- приглашения


@router.get("/admin/invites", response_model=list[InviteRead])
async def list_invites(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("super_admin")),  # noqa: B008
):
    invites = await access.list_invites(db)
    return await _invite_reads(db, invites)


@router.post("/admin/invites", response_model=InviteRead, status_code=201)
async def create_invite(
    body: InviteCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("super_admin")),  # noqa: B008
):
    ip, ua = _meta(request)
    invite, token = await access.create_invite(
        db,
        email=str(body.email),
        role=body.role,
        actor=actor,
        ttl_hours=body.ttl_hours,
        ip=ip,
        user_agent=ua,
    )
    await db.commit()

    url = access.invite_url(token)
    background_tasks.add_task(
        send_invite_email,
        invite.email,
        url,
        access.ROLE_LABELS.get(invite.role, invite.role),
        actor.email,
        invite.expires_at.strftime("%d.%m.%Y %H:%M"),
    )

    read = (await _invite_reads(db, [invite]))[0]
    read.invite_url = url
    logger.info("invite_created_api", invite_id=str(invite.id))
    return read


@router.post("/admin/invites/{invite_id}/resend", response_model=InviteRead)
async def resend_invite(
    invite_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("super_admin")),  # noqa: B008
):
    import uuid as _uuid

    try:
        target_id = _uuid.UUID(invite_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc

    ip, ua = _meta(request)
    invite, token = await access.resend_invite(
        db, target_id, actor, ip=ip, user_agent=ua
    )
    await db.commit()

    url = access.invite_url(token)
    background_tasks.add_task(
        send_invite_email,
        invite.email,
        url,
        access.ROLE_LABELS.get(invite.role, invite.role),
        actor.email,
        invite.expires_at.strftime("%d.%m.%Y %H:%M"),
    )

    read = (await _invite_reads(db, [invite]))[0]
    read.invite_url = url
    return read


@router.delete("/admin/invites/{invite_id}", response_model=MessageResponse)
async def revoke_invite(
    invite_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("super_admin")),  # noqa: B008
):
    import uuid as _uuid

    try:
        target_id = _uuid.UUID(invite_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc

    ip, ua = _meta(request)
    await access.revoke_invite(db, target_id, actor, ip=ip, user_agent=ua)
    await db.commit()
    return MessageResponse(message="Приглашение отозвано.")


# ---------------------------------------------------------------- журнал


@router.get("/admin/audit", response_model=AuditPage)
async def audit_page(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    action: str | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("super_admin")),  # noqa: B008
):
    filters = []
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)
    if action:
        filters.append(AuditLog.action == action)
    if search:
        needle = f"%{search.strip().lower()}%"
        filters.append(
            func.lower(func.coalesce(AuditLog.actor_label, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.target_label, "")).like(needle)
        )

    base = select(AuditLog)
    if filters:
        base = base.where(*filters)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = await db.execute(
        base.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        AuditEntry(
            id=str(row.id),
            created_at=row.created_at,
            actor_label=row.actor_label,
            action=row.action,
            target_label=row.target_label,
            result=row.result,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
        )
        for row in rows.scalars().all()
    ]
    return AuditPage(items=items, total=int(total))
