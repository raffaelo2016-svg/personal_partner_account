import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.exceptions import InvalidCredentials
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.partner import Partner
from app.models.settings import NotificationPreference
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserRead,
)
from app.services.audit import audit_log
from app.services.auth_service import (
    authenticate_user,
    create_tokens,
    refresh_access_token,
    register_user,
    revoke_access_token,
    revoke_refresh_token,
)
from app.services.notification_service import create_notification

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    ip = request.client.host if request.client else None
    user = await authenticate_user(db, body.email, body.password)
    access_token, refresh_token = await create_tokens(user)
    _set_refresh_cookie(response, refresh_token)
    logger.info("login_success", user_id=str(user.id), role=user.role, ip=ip)
    return TokenResponse(
        access_token=access_token,
        user=UserRead(id=str(user.id), email=user.email, role=user.role),
    )


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    if not refresh_cookie:
        raise InvalidCredentials()
    new_token = await refresh_access_token(db, refresh_cookie)
    return RefreshResponse(access_token=new_token)


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),  # noqa: B008
):
    if refresh_cookie:
        await revoke_refresh_token(refresh_cookie)
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        await revoke_access_token(auth_header.split(" ", 1)[1].strip())
    _clear_refresh_cookie(response)
    return {"detail": "Logged out"}


@router.post("/register", response_model=RegisterResponse, status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User | None = Depends(get_current_user_optional),  # noqa: B008
):
    ip = request.client.host if request.client else None

    # Публичная форма регистрации требует капчу, если ключ сконфигурирован.
    # Bearer-токен админа оставлен как совместимый обход для служебных сценариев.
    is_admin_bypass = current_user is not None and current_user.role == "admin"
    if not is_admin_bypass and settings.YANDEX_CAPTCHA_SECRET_KEY:
        from app.services.captcha_service import verify_captcha

        if not body.captcha_token:
            logger.warning("register_captcha_missing", ip=ip)
            raise HTTPException(
                status_code=400,
                detail={"code": "CAPTCHA_REQUIRED", "message": "Подтвердите, что вы не робот"},
            )
        if not await verify_captcha(body.captcha_token, ip):
            logger.warning("register_captcha_invalid", ip=ip)
            raise HTTPException(
                status_code=400,
                detail={"code": "CAPTCHA_INVALID", "message": "Капча не прошла проверку"},
            )

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        logger.warning("register_failed", reason="duplicate_email", ip=ip)
        raise HTTPException(
            status_code=409,
            detail={"code": "DUPLICATE_EMAIL", "message": "Email already registered"},
        )

    user = await register_user(db, body.email, body.password, role="partner")

    partner = Partner(
        user_id=user.id,
        partner_type=body.partner_type,
        company_name=body.company_name,
        director_name=body.director_name,
        inn=body.inn,
        phone=body.phone,
        short_name=body.short_name,
        full_legal_name=body.full_legal_name,
        legal_address=body.legal_address,
        postal_address=body.postal_address,
        kpp=body.kpp,
        court_fee_per_client=1_500_000,
        payment_term_days=10,
        status="pending",
    )
    db.add(partner)
    await db.flush()

    from app.services.chat_service import ensure_rooms_for_partner

    await ensure_rooms_for_partner(db, str(partner.id))

    admins = (
        (
            await db.execute(
                select(User)
                .outerjoin(NotificationPreference, NotificationPreference.user_id == User.id)
                .where(
                    User.role == "admin",
                    User.is_active.is_(True),
                    or_(
                        NotificationPreference.user_id.is_(None),
                        NotificationPreference.new_partner_notifications.is_(True),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    for admin in admins:
        await create_notification(
            db,
            user_id=str(admin.id),
            notif_type="new_partner",
            title="Новый партнёр ожидает активации",
            message=f"{body.company_name} зарегистрирован в кабинете",
            link=f"/admin/partners/{partner.id}",
        )

    await db.commit()

    audit_log(action="partner_registered", user_id=str(user.id), target_id=str(partner.id), target_type="partner")
    logger.info(
        "partner_registered",
        user_id=str(user.id),
        partner_id=str(partner.id),
        company=body.company_name,
        ip=ip,
    )

    return RegisterResponse(
        message="Registration successful. Awaiting admin approval.",
        user=UserRead(id=str(user.id), email=user.email, role=user.role),
    )


@router.get("/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    company_name: str | None = None
    if current_user.role == "partner":
        row = await db.execute(
            select(Partner).where(Partner.user_id == current_user.id, Partner.deleted_at.is_(None)),
        )
        partner = row.scalar_one_or_none()
        if partner:
            company_name = partner.company_name
    return UserRead(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        company_name=company_name,
    )
