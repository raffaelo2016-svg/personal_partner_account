"""Управление доступами администраторов: bootstrap, приглашения, роли, журнал."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import redis_client
from app.core.security import hash_password
from app.models.invite import BootstrapToken, Invite
from app.models.user import User
from app.services.audit import audit_log

logger = structlog.get_logger()

INVITE_ROLES = {"admin", "super_admin", "agent"}
ROLE_LABELS = {"admin": "Администратор", "super_admin": "Супер-администратор", "agent": "Агент"}
DEFAULT_INVITE_TTL_HOURS = 72
ALLOWED_INVITE_TTL_HOURS = {24, 72, 168}

INVITE_TOKEN_PREFIX = "invite_token:"

LOGIN_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_login(value: str) -> str:
    return value.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _fail(code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST) -> None:
    raise HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
        headers={"code": code},
    )


def _validate_password(password: str, *, email: str, login: str) -> None:
    if len(password) < 10:
        _fail("WEAK_PASSWORD", "Пароль должен содержать минимум 10 символов")
    if not re.search(r"[A-Za-zА-Яа-я]", password) or not re.search(r"\d", password):
        _fail("WEAK_PASSWORD", "Пароль должен содержать буквы и цифры")
    if password.lower() in {email.lower(), login.lower()}:
        _fail("WEAK_PASSWORD", "Пароль не должен совпадать с почтой или логином")


def _validate_login(login: str) -> None:
    if not LOGIN_RE.match(login):
        _fail(
            "INVALID_LOGIN",
            "Логин: 3–32 символа, латинские буквы, цифры, точка, дефис или подчёркивание",
        )


async def _email_taken(session: AsyncSession, email: str) -> bool:
    row = await session.execute(select(User.id).where(func.lower(User.email) == email))
    return row.first() is not None


async def _login_taken(session: AsyncSession, login: str) -> bool:
    row = await session.execute(select(User.id).where(func.lower(User.login) == login))
    return row.first() is not None


async def store_invite_token(invite: Invite, token: str) -> None:
    """Хранит токен приглашения в Redis до истечения срока, чтобы ссылку можно было скопировать позже."""
    ttl = int((invite.expires_at - datetime.now(UTC)).total_seconds())
    if ttl > 0:
        await redis_client.setex(f"{INVITE_TOKEN_PREFIX}{invite.id}", ttl, token)


async def get_invite_token(invite_id) -> str | None:
    value = await redis_client.get(f"{INVITE_TOKEN_PREFIX}{invite_id}")
    return value if isinstance(value, str) else None


async def drop_invite_token(invite_id) -> None:
    await redis_client.delete(f"{INVITE_TOKEN_PREFIX}{invite_id}")


def invite_url(token: str) -> str:
    return f"{settings.PUBLIC_APP_URL.rstrip('/')}/invite/{token}"


# ---------------------------------------------------------------- супер-админы


async def count_active_super_admins(session: AsyncSession) -> int:
    row = await session.execute(select(func.count(User.id)).where(User.role == "super_admin", User.is_active.is_(True)))
    return int(row.scalar_one())


async def needs_setup(session: AsyncSession) -> bool:
    row = await session.execute(select(func.count(User.id)).where(User.role == "super_admin"))
    return int(row.scalar_one()) == 0


async def create_bootstrap_key(session: AsyncSession, ttl_minutes: int = 60) -> tuple[str, datetime]:
    """Создаёт одноразовый ключ первичной настройки и возвращает его открытым текстом."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    session.add(BootstrapToken(token_hash=_token_hash(token), expires_at=expires_at))
    await session.flush()
    logger.warning("bootstrap_key_created", expires_at=expires_at.isoformat())
    return token, expires_at


async def consume_bootstrap_key(
    session: AsyncSession,
    *,
    key: str,
    email: str,
    login: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    if not await needs_setup(session):
        _fail("SETUP_ALREADY_DONE", "Первый супер-администратор уже создан", status.HTTP_409_CONFLICT)

    row = await session.execute(select(BootstrapToken).where(BootstrapToken.token_hash == _token_hash(key)))
    token = row.scalar_one_or_none()
    now = datetime.now(UTC)
    if token is None or token.used_at is not None or token.expires_at < now:
        _fail("BOOTSTRAP_KEY_INVALID", "Ключ недействителен или истёк", status.HTTP_400_BAD_REQUEST)

    email = normalize_email(email)
    login = normalize_login(login)
    if not EMAIL_RE.match(email):
        _fail("INVALID_EMAIL", "Некорректная почта")
    _validate_login(login)
    _validate_password(password, email=email, login=login)
    if await _email_taken(session, email):
        _fail("EMAIL_TAKEN", "Эта почта уже используется", status.HTTP_409_CONFLICT)
    if await _login_taken(session, login):
        _fail("LOGIN_TAKEN", "Этот логин уже занят", status.HTTP_409_CONFLICT)

    user = User(
        email=email,
        login=login,
        hashed_password=hash_password(password),
        role="super_admin",
        is_active=True,
        password_changed_at=now,
    )
    session.add(user)
    token.used_at = now
    await session.flush()

    audit_log(
        action="bootstrap_completed",
        user_id=str(user.id),
        actor_label=email,
        target_id=str(user.id),
        target_type="user",
        target_label=email,
        ip_address=ip,
        user_agent=user_agent,
    )
    logger.info("bootstrap_completed", user_id=str(user.id))
    return user


# ---------------------------------------------------------------- приглашения


async def _revoke_active_invites(session: AsyncSession, email: str, *, except_id=None) -> None:
    row = await session.execute(
        select(Invite).where(
            func.lower(Invite.email) == email,
            Invite.used_at.is_(None),
            Invite.revoked_at.is_(None),
            Invite.expires_at > datetime.now(UTC),
        )
    )
    for invite in row.scalars().all():
        if except_id is not None and invite.id == except_id:
            continue
        invite.revoked_at = datetime.now(UTC)


async def create_invite(
    session: AsyncSession,
    *,
    email: str,
    role: str,
    actor: User,
    ttl_hours: int = DEFAULT_INVITE_TTL_HOURS,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[Invite, str]:
    email = normalize_email(email)
    if not EMAIL_RE.match(email):
        _fail("INVALID_EMAIL", "Некорректная почта")
    if role not in INVITE_ROLES:
        _fail("INVALID_ROLE", "Недопустимая роль")
    if ttl_hours not in ALLOWED_INVITE_TTL_HOURS:
        _fail("INVALID_TTL", "Срок действия: 24, 72 или 168 часов")
    if await _email_taken(session, email):
        _fail("EMAIL_TAKEN", "У этой почты уже есть аккаунт", status.HTTP_409_CONFLICT)

    await _revoke_active_invites(session, email)

    token = secrets.token_urlsafe(48)
    invite = Invite(
        email=email,
        role=role,
        token_hash=_token_hash(token),
        expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        created_by=actor.id,
    )
    session.add(invite)
    await session.flush()
    await store_invite_token(invite, token)

    audit_log(
        action="invite_created",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(invite.id),
        target_type="invite",
        target_label=email,
        details={"role": role, "ttl_hours": ttl_hours},
        ip_address=ip,
        user_agent=user_agent,
    )
    logger.info("invite_created", invite_id=str(invite.id), role=role)
    return invite, token


async def revoke_invite(session: AsyncSession, invite_id, actor: User, *, ip=None, user_agent=None) -> Invite:
    invite = await session.get(Invite, invite_id)
    if invite is None:
        _fail("INVITE_NOT_FOUND", "Приглашение не найдено", status.HTTP_404_NOT_FOUND)
    if invite.used_at is not None:
        _fail("INVITE_USED", "Приглашение уже использовано", status.HTTP_409_CONFLICT)
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
        await drop_invite_token(invite.id)
        await session.flush()
    audit_log(
        action="invite_revoked",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(invite.id),
        target_type="invite",
        target_label=invite.email,
        ip_address=ip,
        user_agent=user_agent,
    )
    return invite


async def resend_invite(
    session: AsyncSession,
    invite_id,
    actor: User,
    *,
    ttl_hours: int = DEFAULT_INVITE_TTL_HOURS,
    ip=None,
    user_agent=None,
) -> tuple[Invite, str]:
    old = await session.get(Invite, invite_id)
    if old is None:
        _fail("INVITE_NOT_FOUND", "Приглашение не найдено", status.HTTP_404_NOT_FOUND)
    new_invite, token = await create_invite(
        session,
        email=old.email,
        role=old.role,
        actor=actor,
        ttl_hours=ttl_hours,
        ip=ip,
        user_agent=user_agent,
    )
    if old.revoked_at is None and old.used_at is None:
        old.revoked_at = datetime.now(UTC)
    await session.flush()
    audit_log(
        action="invite_resent",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(new_invite.id),
        target_type="invite",
        target_label=new_invite.email,
        ip_address=ip,
        user_agent=user_agent,
    )
    return new_invite, token


async def get_invite_by_token(session: AsyncSession, token: str) -> Invite | None:
    if not token:
        return None
    row = await session.execute(select(Invite).where(Invite.token_hash == _token_hash(token)))
    return row.scalar_one_or_none()


async def accept_invite(
    session: AsyncSession,
    *,
    token: str,
    login: str,
    password: str,
    full_name: str | None = None,
    phone: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    invite = await get_invite_by_token(session, token)
    if invite is None:
        _fail("INVITE_INVALID", "Ссылка недействительна")
    if invite.used_at is not None:
        _fail("INVITE_USED", "Ссылка уже использована", status.HTTP_410_GONE)
    if invite.revoked_at is not None:
        _fail("INVITE_REVOKED", "Приглашение отозвано", status.HTTP_410_GONE)
    if invite.expires_at < datetime.now(UTC):
        _fail("INVITE_EXPIRED", "Срок действия ссылки истёк", status.HTTP_410_GONE)

    login = normalize_login(login)
    _validate_login(login)
    _validate_password(password, email=invite.email, login=login)

    if await _login_taken(session, login):
        _fail("LOGIN_TAKEN", "Этот логин уже занят", status.HTTP_409_CONFLICT)
    if await _email_taken(session, invite.email):
        _fail("EMAIL_TAKEN", "У этой почты уже есть аккаунт", status.HTTP_409_CONFLICT)

    user = User(
        email=invite.email,
        login=login,
        hashed_password=hash_password(password),
        role=invite.role if invite.role in INVITE_ROLES else "admin",
        is_active=True,
        created_by=invite.created_by,
        password_changed_at=datetime.now(UTC),
    )
    session.add(user)
    invite.used_at = datetime.now(UTC)
    await drop_invite_token(invite.id)
    await session.flush()

    if user.role == "agent":
        from app.services.agent_service import create_agent_profile

        await create_agent_profile(
            session,
            user,
            full_name=(full_name or invite.email.split("@")[0]).strip(),
            phone=(phone or "").strip(),
        )

    audit_log(
        action="invite_accepted",
        user_id=str(user.id),
        actor_label=invite.email,
        target_id=str(user.id),
        target_type="user",
        target_label=invite.email,
        details={"role": user.role},
        ip_address=ip,
        user_agent=user_agent,
    )
    logger.info("invite_accepted", user_id=str(user.id), role=user.role)
    return user


async def list_invites(session: AsyncSession) -> list[Invite]:
    row = await session.execute(select(Invite).order_by(Invite.created_at.desc()))
    return list(row.scalars().all())


# ---------------------------------------------------------------- пользователи


async def list_admins(session: AsyncSession, search: str | None = None) -> list[User]:
    query = select(User).where(User.role.in_(["admin", "super_admin"])).order_by(User.created_at)
    if search:
        needle = f"%{search.strip().lower()}%"
        query = query.where(
            func.lower(User.email).like(needle) | func.lower(func.coalesce(User.login, "")).like(needle)
        )
    row = await session.execute(query)
    return list(row.scalars().all())


async def update_admin(
    session: AsyncSession,
    *,
    target_id,
    actor: User,
    role: str | None = None,
    is_active: bool | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    target = await session.get(User, target_id)
    if target is None or target.role not in ("admin", "super_admin"):
        _fail("USER_NOT_FOUND", "Администратор не найден", status.HTTP_404_NOT_FOUND)

    new_role = role if role is not None else target.role
    new_active = is_active if is_active is not None else target.is_active

    if role is not None and role not in INVITE_ROLES:
        _fail("INVALID_ROLE", "Недопустимая роль")

    if str(target.id) == str(actor.id):
        if is_active is False:
            _fail("SELF_ACTION_FORBIDDEN", "Нельзя заблокировать самого себя")
        if role is not None and role != target.role:
            _fail("SELF_ACTION_FORBIDDEN", "Нельзя изменить свою роль")

    losing_super = target.role == "super_admin" and (new_role != "super_admin" or new_active is False)
    if losing_super and await count_active_super_admins(session) <= 1:
        _fail(
            "LAST_SUPER_ADMIN",
            "В системе должен остаться хотя бы один активный супер-администратор",
            status.HTTP_409_CONFLICT,
        )

    changed = {}
    if role is not None and role != target.role:
        changed["role"] = {"from": target.role, "to": role}
        target.role = role
    if is_active is not None and is_active != target.is_active:
        changed["is_active"] = {"from": target.is_active, "to": is_active}
        target.is_active = is_active

    await session.flush()

    if changed:
        action = (
            "user_blocked" if is_active is False else ("user_unblocked" if is_active is True else "user_role_changed")
        )
        audit_log(
            action=action,
            user_id=str(actor.id),
            actor_label=actor.email,
            target_id=str(target.id),
            target_type="user",
            target_label=target.email,
            details=changed,
            ip_address=ip,
            user_agent=user_agent,
        )

    return target


# ---------------------------------------------------------------- миграция


async def find_shared_admin(session: AsyncSession, email: str | None = None) -> User | None:
    """Находит общую (устаревшую) учётную запись администратора."""
    if email:
        row = await session.execute(select(User).where(func.lower(User.email) == normalize_email(email)))
        user = row.scalar_one_or_none()
        if user is None or user.role not in ("admin", "super_admin"):
            return None
        return user

    row = await session.execute(
        select(User).where(
            User.is_legacy_shared.is_(True),
            User.role.in_(["admin", "super_admin"]),
        )
    )
    found = row.scalars().all()
    if len(found) == 1:
        return found[0]

    # Резервный вариант: единственный администратор без личного логина.
    candidates = (
        (
            await session.execute(
                select(User).where(
                    User.role == "admin",
                    User.login.is_(None),
                    User.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return candidates[0] if len(candidates) == 1 else None


async def disable_shared_admin(
    session: AsyncSession,
    user: User,
    *,
    actor_label: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    if user.role not in ("admin", "super_admin"):
        _fail("USER_NOT_FOUND", "Администратор не найден", status.HTTP_404_NOT_FOUND)
    if user.role == "super_admin" and await count_active_super_admins(session) <= 1:
        _fail(
            "LAST_SUPER_ADMIN",
            "Нельзя отключить последнего супер-администратора",
            status.HTTP_409_CONFLICT,
        )

    user.is_active = False
    user.is_legacy_shared = True
    await session.flush()

    audit_log(
        action="shared_account_disabled",
        user_id=str(user.id),
        actor_label=actor_label or "migration",
        target_id=str(user.id),
        target_type="user",
        target_label=user.email,
        ip_address=ip,
        user_agent=user_agent,
    )
    logger.warning("shared_account_disabled", user_id=str(user.id))
    return user


async def bulk_invite(
    session: AsyncSession,
    *,
    emails: list[str],
    role: str,
    actor: User,
    ttl_hours: int = DEFAULT_INVITE_TTL_HOURS,
) -> tuple[list[tuple[Invite, str]], list[tuple[str, str]]]:
    """Создаёт приглашения пачкой. Возвращает (успешные, ошибки)."""
    created: list[tuple[Invite, str]] = []
    failed: list[tuple[str, str]] = []
    for email in emails:
        try:
            invite, token = await create_invite(
                session,
                email=email,
                role=role,
                actor=actor,
                ttl_hours=ttl_hours,
            )
            created.append((invite, token))
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            failed.append((email, detail.get("message") or "Не удалось создать приглашение"))
    return created, failed
