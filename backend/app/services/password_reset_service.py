import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import redis_client
from app.core.security import hash_password
from app.models.user import User
from app.services.audit import audit_log
from app.services.email_service import send_password_reset_email

logger = structlog.get_logger()

TOKEN_KEY_PREFIX = "password_reset:token:"
USER_KEY_PREFIX = "password_reset:user:"


@dataclass(frozen=True)
class PasswordResetDelivery:
    recipient: str
    reset_url: str
    token_key: str
    user_key: str
    user_id: str


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def request_password_reset(session: AsyncSession, email: str) -> PasswordResetDelivery | None:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        logger.info("password_reset_requested_unknown_email")
        return None

    token = secrets.token_urlsafe(48)
    digest = _token_digest(token)
    ttl = settings.PASSWORD_RESET_EXPIRE_MINUTES * 60
    user_key = f"{USER_KEY_PREFIX}{user.id}"

    previous_digest = await redis_client.get(user_key)
    if previous_digest:
        await redis_client.delete(f"{TOKEN_KEY_PREFIX}{previous_digest}")

    token_key = f"{TOKEN_KEY_PREFIX}{digest}"
    await redis_client.setex(token_key, ttl, str(user.id))
    await redis_client.setex(user_key, ttl, digest)

    base_url = settings.PUBLIC_APP_URL.rstrip("/")
    return PasswordResetDelivery(
        recipient=user.email,
        reset_url=f"{base_url}/reset-password?token={token}",
        token_key=token_key,
        user_key=user_key,
        user_id=str(user.id),
    )


async def deliver_password_reset(delivery: PasswordResetDelivery) -> None:
    delivered = await send_password_reset_email(delivery.recipient, delivery.reset_url)
    if not delivered:
        await redis_client.delete(delivery.token_key, delivery.user_key)
        logger.error("password_reset_delivery_unavailable", user_id=delivery.user_id)
        return

    audit_log(action="password_reset_requested", user_id=delivery.user_id)
    logger.info("password_reset_email_sent", user_id=delivery.user_id)


async def reset_password(session: AsyncSession, token: str, new_password: str) -> bool:
    digest = _token_digest(token)
    token_key = f"{TOKEN_KEY_PREFIX}{digest}"
    user_id = await redis_client.get(token_key)
    if not user_id:
        return False

    user_key = f"{USER_KEY_PREFIX}{user_id}"
    if await redis_client.get(user_key) != digest:
        await redis_client.delete(token_key)
        return False

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        await redis_client.delete(token_key, user_key)
        return False

    user.hashed_password = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    await session.commit()
    await redis_client.delete(token_key, user_key)
    audit_log(action="password_reset_completed", user_id=str(user.id))
    logger.info("password_reset_completed", user_id=str(user.id))
    return True
