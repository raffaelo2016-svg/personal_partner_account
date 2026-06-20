import uuid

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db

logger = structlog.get_logger()
bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    from app.models.partner import Partner
    from app.models.user import User

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    from app.services.auth_service import is_access_jti_revoked

    if await is_access_jti_revoked(payload.get("jti", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"code": "TOKEN_REVOKED"},
        )
    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    if user.role == "partner":
        row = await db.execute(select(Partner).where(Partner.user_id == user.id, Partner.deleted_at.is_(None)))
        partner = row.scalar_one_or_none()
        if partner and partner.status in ("blocked", "pending"):
            logger.warning(
                "access_denied",
                user_id=str(user.id),
                reason=f"partner_{partner.status}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
                headers={"code": f"PARTNER_{partner.status.upper()}"},
            )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Попытаться достать текущего юзера. При любой ошибке (нет токена, невалиден, отозван) — None."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


def require_role(*roles: str):
    async def checker(current_user=Depends(get_current_user)):  # noqa: B008
        if current_user.role not in roles:
            logger.warning(
                "role_access_denied",
                user_id=str(current_user.id),
                user_role=current_user.role,
                required_roles=list(roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
                headers={"code": "FORBIDDEN"},
            )
        return current_user

    return checker
