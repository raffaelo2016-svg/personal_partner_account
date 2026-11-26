"""Людские подписи в задаче: вместо почты — имя и фамилия.

В кабинете у партнёра имя хранится в карточке партнёра, у сотрудника — в
``users.full_name``. Эти подписи показываются в обсуждении задачи, истории
и у загруженных файлов, чтобы вместо адреса почты было человеческое имя.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner
from app.models.user import User

STAFF_LABEL = "Сотрудник ЮРИТЕХ"
PARTNER_LABEL = "Партнёр"
AGENT_LABEL = "Агент"
MEMBER_LABEL = "Участник"

ADMIN_ROLES = ("admin", "super_admin")


def _squeeze(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def partner_display_name(partner: Partner | None) -> str | None:
    """Имя партнёра: сначала ФИО руководителя, затем название компании."""
    if partner is None:
        return None
    return _squeeze(partner.director_name) or _squeeze(partner.company_name) or None


def _label_for(user: User | None, partner_name: str | None) -> str:
    if user is None:
        return MEMBER_LABEL
    if user.role == "partner":
        return partner_name or _squeeze(user.full_name) or PARTNER_LABEL
    full_name = _squeeze(user.full_name)
    if full_name:
        return full_name
    if user.role in ADMIN_ROLES:
        return STAFF_LABEL
    if user.role == "agent":
        return AGENT_LABEL
    return MEMBER_LABEL


def user_display_name(user: User | None, partner: Partner | None = None) -> str:
    """Подпись одного автора, когда карточка партнёра уже под рукой."""
    return _label_for(user, partner_display_name(partner))


async def resolve_display_names(
    session: AsyncSession,
    user_ids: Iterable[uuid.UUID | None],
) -> dict[uuid.UUID, str]:
    """Подписи пачкой одним запросом — для авторов сообщений, событий и файлов."""
    ids = {user_id for user_id in user_ids if user_id is not None}
    if not ids:
        return {}
    rows = await session.execute(
        select(User, Partner.director_name, Partner.company_name)
        .outerjoin(Partner, Partner.user_id == User.id)
        .where(User.id.in_(ids))
    )
    names: dict[uuid.UUID, str] = {}
    for user, director_name, company_name in rows.all():
        partner_name = _squeeze(director_name) or _squeeze(company_name) or None
        names[user.id] = _label_for(user, partner_name)
    return names


def name_from(names: Mapping[uuid.UUID, str] | None, user_id: uuid.UUID | None) -> str | None:
    if names is None or user_id is None:
        return None
    return names.get(user_id)
