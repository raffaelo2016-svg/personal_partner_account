import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import InvalidCredentials, PartnerBlocked, PartnerPending
from app.core.redis import redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.partner import Partner
from app.models.user import User
from app.services.audit import audit_log

logger = structlog.get_logger()

REFRESH_KEY_PREFIX = "refresh:"
ACCESS_BLACKLIST_PREFIX = "access_bl:"


_DUMMY_HASH = "$2b$12$ufHqSMMTWS003hgZSvaUoe/0wnX8CRv5uNGMECZBwjwf2qec9aw.a"


async def is_access_jti_revoked(jti: str) -> bool:
    if not jti:
        return False
    value = await redis_client.get(f"{ACCESS_BLACKLIST_PREFIX}{jti}")
    # redis_client is configured with decode_responses=True, so a real hit
    # returns the string "1". Anything else (None, missing, non-str) = not revoked.
    return isinstance(value, str) and value == "1"


async def revoke_access_token(token: str) -> None:
    """Поместить access-token в blacklist до истечения его exp."""
    import jwt

    from app.core.security import ALGORITHM

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        return
    if payload.get("type") != "access":
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    from datetime import UTC, datetime

    ttl = int(exp - datetime.now(UTC).timestamp())
    if ttl <= 0:
        return
    await redis_client.setex(f"{ACCESS_BLACKLIST_PREFIX}{jti}", ttl, "1")


async def authenticate_user(session: AsyncSession, identifier: str, password: str) -> User:
    needle = (identifier or "").strip().lower()
    result = await session.execute(
        select(User).where(
            or_(func.lower(User.email) == needle, func.lower(User.login) == needle)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        # Constant-time: always run bcrypt even when user doesn't exist
        verify_password(password, _DUMMY_HASH)
        audit_log(action="login_failed", details={"identifier": needle})
        logger.warning("login_failed", reason="user_not_found")
        raise InvalidCredentials()
    if not verify_password(password, user.hashed_password):
        audit_log(action="login_failed", details={"identifier": needle})
        logger.warning("login_failed", user_id=str(user.id), reason="wrong_password")
        raise InvalidCredentials()
    if not user.is_active:
        audit_log(action="login_failed", user_id=str(user.id), details={"reason": "inactive"})
        logger.warning("login_failed", user_id=str(user.id), reason="inactive")
        raise InvalidCredentials()

    if user.role == "partner":
        row = await session.execute(
            select(Partner).where(Partner.user_id == user.id, Partner.deleted_at.is_(None)),
        )
        partner = row.scalar_one_or_none()
        if partner and partner.status == "pending":
            audit_log(action="login_failed", user_id=str(user.id), details={"reason": "partner_pending"})
            logger.warning("login_failed", user_id=str(user.id), reason="partner_pending")
            raise PartnerPending()
        if partner and partner.status == "blocked":
            audit_log(action="login_failed", user_id=str(user.id), details={"reason": "partner_blocked"})
            logger.warning("login_failed", user_id=str(user.id), reason="partner_blocked")
            raise PartnerBlocked()

    logger.info("user_authenticated", user_id=str(user.id), role=user.role)
    return user


async def create_tokens(user: User) -> tuple[str, str]:
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    payload = decode_refresh_token(refresh_token)
    jti = payload["jti"]
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis_client.setex(f"{REFRESH_KEY_PREFIX}{jti}", ttl, str(user.id))

    logger.info("tokens_issued", user_id=str(user.id), role=user.role)
    return access_token, refresh_token


async def refresh_access_token(session: AsyncSession, refresh_token_str: str) -> str:
    payload = decode_refresh_token(refresh_token_str)
    jti = payload.get("jti")
    user_id = payload.get("sub")

    if not jti or not user_id:
        logger.warning("refresh_failed", reason="invalid_payload")
        raise InvalidCredentials()

    stored = await redis_client.get(f"{REFRESH_KEY_PREFIX}{jti}")
    if stored is None or stored != user_id:
        logger.warning("refresh_failed", user_id=user_id, reason="token_not_in_redis")
        raise InvalidCredentials()

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        logger.warning("refresh_failed", user_id=user_id, reason="user_inactive_or_missing")
        raise InvalidCredentials()

    new_access = create_access_token({"sub": str(user.id), "role": user.role})
    audit_log(action="token_refresh", user_id=str(user.id), actor_label=user.email)
    logger.info("token_refreshed", user_id=str(user.id))
    return new_access


async def revoke_refresh_token(refresh_token_str: str) -> None:
    try:
        payload = decode_refresh_token(refresh_token_str)
        jti = payload.get("jti")
        if jti:
            await redis_client.delete(f"{REFRESH_KEY_PREFIX}{jti}")
            audit_log(action="logout", user_id=payload.get("sub"))
            logger.info("user_logged_out", user_id=payload.get("sub"))
    except Exception:  # noqa: BLE001
        logger.debug("revoke_refresh_token_failed")


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    role: str = "partner",
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    logger.info("user_registered", user_id=str(user.id), email=email, role=role)
    return user
