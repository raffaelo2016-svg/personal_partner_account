"""Агентский кабинет: профиль агента, закрепление партнёров, начисления и выплаты."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent, AgentAccrual, AgentPayoutRequest
from app.models.client import Client
from app.models.partner import Partner
from app.models.user import User
from app.services.audit import audit_log

logger = structlog.get_logger()

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ACTIVE_PAYOUT_STATUSES = ("submitted", "checking", "scheduled", "needs_fix")
PAYOUT_STATUSES = ("submitted", "checking", "scheduled", "paid", "needs_fix", "cancelled")


def _fail(code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST) -> None:
    raise HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
        headers={"code": code},
    )


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


async def _unique_code(session: AsyncSession) -> str:
    for _ in range(20):
        code = _generate_code()
        exists = await session.execute(select(Agent.id).where(Agent.code == code))
        if exists.first() is None:
            return code
    raise RuntimeError("Не удалось сгенерировать код агента")


async def get_agent_by_user(session: AsyncSession, user_id) -> Agent | None:
    row = await session.execute(select(Agent).where(Agent.user_id == user_id))
    return row.scalar_one_or_none()


async def get_agent_by_code(session: AsyncSession, code: str) -> Agent | None:
    if not code:
        return None
    row = await session.execute(select(Agent).where(Agent.code == code.strip().upper()))
    return row.scalar_one_or_none()


async def create_agent_profile(
    session: AsyncSession,
    user: User,
    *,
    full_name: str,
    phone: str = "",
    company_name: str | None = None,
) -> Agent:
    agent = Agent(
        user_id=user.id,
        code=await _unique_code(session),
        full_name=full_name.strip(),
        phone=phone.strip(),
        company_name=company_name,
        status="active",
    )
    session.add(agent)
    await session.flush()
    audit_log(
        action="agent_created",
        user_id=str(user.id),
        actor_label=user.email,
        target_id=str(agent.id),
        target_type="agent",
        target_label=agent.full_name,
    )
    logger.info("agent_created", agent_id=str(agent.id), code=agent.code)
    return agent


async def link_partner_by_code(session: AsyncSession, partner: Partner, code: str | None) -> Agent | None:
    """Закрепляет нового партнёра за агентом по реферальному коду."""
    if not code:
        return None
    agent = await get_agent_by_code(session, code)
    if agent is None or agent.status != "active":
        logger.warning("agent_code_invalid", code=code)
        return None
    partner.agent_id = agent.id
    partner.agent_linked_at = datetime.now(UTC)
    await session.flush()
    audit_log(
        action="partner_linked_to_agent",
        actor_label="registration",
        target_id=str(partner.id),
        target_type="partner",
        target_label=partner.company_name,
        details={"agent_id": str(agent.id), "code": agent.code},
    )
    return agent


async def bind_partner_admin(
    session: AsyncSession,
    partner: Partner,
    *,
    agent: Agent | None,
    actor: User,
    reason: str,
    force: bool = False,
) -> Partner:
    """Исправление привязки супер-админом — только с причиной."""
    if partner.agent_id is not None and not force:
        _fail("PARTNER_ALREADY_LINKED", "Партнёр уже закреплён за агентом", status.HTTP_409_CONFLICT)
    if not reason.strip():
        _fail("REASON_REQUIRED", "Укажите причину изменения привязки")

    old_agent_id = str(partner.agent_id) if partner.agent_id else None
    partner.agent_id = agent.id if agent else None
    partner.agent_linked_at = datetime.now(UTC) if agent else None
    await session.flush()

    audit_log(
        action="partner_agent_reassigned",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(partner.id),
        target_type="partner",
        target_label=partner.company_name,
        details={
            "from": old_agent_id,
            "to": str(agent.id) if agent else None,
            "reason": reason,
        },
    )
    return partner


async def accrue_for_client(session: AsyncSession, client: Client) -> AgentAccrual | None:
    """Начисление агенту при введении клиента в процедуру. Одно дело — одно начисление."""
    partner = await session.get(Partner, client.partner_id)
    if partner is None or partner.agent_id is None:
        return None

    existing = await session.execute(
        select(AgentAccrual.id).where(AgentAccrual.client_id == client.id)
    )
    if existing.first() is not None:
        return None

    rate = settings.AGENT_ACCRUAL_RATE
    if rate <= 0:
        return None

    accrual = AgentAccrual(
        agent_id=partner.agent_id,
        partner_id=partner.id,
        client_id=client.id,
        amount=rate,
        rate=rate,
        status="accrued",
        reason="procedure_started",
    )
    session.add(accrual)
    await session.flush()

    audit_log(
        action="agent_accrued",
        actor_label="system",
        target_id=str(accrual.id),
        target_type="agent_accrual",
        target_label=f"client:{client.id}",
        details={"agent_id": str(partner.agent_id), "amount": rate},
    )
    logger.info("agent_accrued", agent_id=str(partner.agent_id), client_id=str(client.id), amount=rate)
    return accrual


# ---------------------------------------------------------------- чтение


async def agent_stats(session: AsyncSession, agent_id) -> dict[str, int]:
    partners = (
        await session.execute(
            select(func.count(Partner.id)).where(
                Partner.agent_id == agent_id, Partner.deleted_at.is_(None)
            )
        )
    ).scalar_one()

    clients = (
        await session.execute(
            select(func.count(Client.id))
            .join(Partner, Client.partner_id == Partner.id)
            .where(Partner.agent_id == agent_id, Client.deleted_at.is_(None))
        )
    ).scalar_one()

    accrued = (
        await session.execute(
            select(func.coalesce(func.sum(AgentAccrual.amount), 0)).where(
                AgentAccrual.agent_id == agent_id, AgentAccrual.status == "accrued"
            )
        )
    ).scalar_one()

    reserved = (
        await session.execute(
            select(func.coalesce(func.sum(AgentPayoutRequest.amount), 0)).where(
                AgentPayoutRequest.agent_id == agent_id,
                AgentPayoutRequest.status.in_(ACTIVE_PAYOUT_STATUSES),
            )
        )
    ).scalar_one()

    paid = (
        await session.execute(
            select(func.coalesce(func.sum(AgentPayoutRequest.amount), 0)).where(
                AgentPayoutRequest.agent_id == agent_id,
                AgentPayoutRequest.status == "paid",
            )
        )
    ).scalar_one()

    return {
        "partners": int(partners),
        "clients": int(clients),
        "accrued": int(accrued),
        "reserved": int(reserved),
        "paid": int(paid),
        "available": max(int(accrued) - int(reserved), 0),
    }


async def list_agent_partners(session: AsyncSession, agent_id) -> list[Partner]:
    row = await session.execute(
        select(Partner)
        .where(Partner.agent_id == agent_id, Partner.deleted_at.is_(None))
        .order_by(Partner.agent_linked_at.desc())
    )
    return list(row.scalars().all())


async def list_accruals(session: AsyncSession, agent_id, limit: int = 200) -> list[AgentAccrual]:
    row = await session.execute(
        select(AgentAccrual)
        .where(AgentAccrual.agent_id == agent_id)
        .order_by(AgentAccrual.created_at.desc())
        .limit(limit)
    )
    return list(row.scalars().all())


async def list_payouts(session: AsyncSession, agent_id) -> list[AgentPayoutRequest]:
    row = await session.execute(
        select(AgentPayoutRequest)
        .where(AgentPayoutRequest.agent_id == agent_id)
        .order_by(AgentPayoutRequest.created_at.desc())
    )
    return list(row.scalars().all())


# ---------------------------------------------------------------- выплаты


def _payout_period(now: datetime | None = None) -> str:
    """Заявка до 14-го включительно попадает в выплату 15-го, позже — в следующий цикл."""
    now = now or datetime.now(UTC)
    year, month = now.year, now.month
    if now.day > 14:
        month += 1
        if month > 12:
            month = 1
            year += 1
    return f"{year:04d}-{month:02d}"


async def create_payout_request(session: AsyncSession, agent: Agent) -> AgentPayoutRequest:
    active = await session.execute(
        select(AgentPayoutRequest.id).where(
            AgentPayoutRequest.agent_id == agent.id,
            AgentPayoutRequest.status.in_(ACTIVE_PAYOUT_STATUSES),
        )
    )
    if active.first() is not None:
        _fail("PAYOUT_EXISTS", "Уже есть активная заявка на выплату", status.HTTP_409_CONFLICT)

    if agent.requisites_status != "accepted":
        _fail("REQUISITES_NOT_ACCEPTED", "Сначала заполните и подтвердите реквизиты")

    stats = await agent_stats(session, agent.id)
    available = stats["available"]
    if available <= 0:
        _fail("NO_AVAILABLE_AMOUNT", "Нет суммы, доступной к выплате")

    request = AgentPayoutRequest(
        agent_id=agent.id,
        amount=available,
        status="submitted",
        period=_payout_period(),
    )
    session.add(request)
    await session.flush()

    audit_log(
        action="agent_payout_requested",
        user_id=str(agent.user_id),
        actor_label=agent.user.email,
        target_id=str(request.id),
        target_type="agent_payout",
        target_label=f"{available}",
        details={"period": request.period, "amount": available},
    )
    return request


async def update_payout_status(
    session: AsyncSession,
    request: AgentPayoutRequest,
    *,
    new_status: str,
    actor: User,
    comment: str | None = None,
) -> AgentPayoutRequest:
    if new_status not in PAYOUT_STATUSES:
        _fail("INVALID_STATUS", "Недопустимый статус заявки")
    if request.status == "paid" and new_status != "paid":
        _fail("PAYOUT_IMMUTABLE", "Выплаченную заявку нельзя изменить", status.HTTP_409_CONFLICT)

    request.status = new_status
    request.reviewed_by = actor.id
    request.reviewed_at = datetime.now(UTC)
    if comment is not None:
        request.comment = comment
    if new_status == "paid":
        request.paid_at = datetime.now(UTC)
    await session.flush()

    audit_log(
        action="agent_payout_status_changed",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(request.id),
        target_type="agent_payout",
        target_label=new_status,
        details={"status": new_status, "comment": comment},
    )
    return request


# ---------------------------------------------------------------- реквизиты


async def save_requisites(
    session: AsyncSession,
    agent: Agent,
    *,
    recipient_type: str,
    data: dict[str, Any],
) -> Agent:
    if recipient_type not in ("individual", "ip", "company"):
        _fail("INVALID_RECIPIENT_TYPE", "Недопустимый тип получателя")

    agent.requisites_recipient_type = recipient_type
    agent.requisites = data
    agent.requisites_status = "sent"
    await session.flush()

    audit_log(
        action="agent_requisites_updated",
        user_id=str(agent.user_id),
        actor_label=agent.user.email,
        target_id=str(agent.id),
        target_type="agent",
        target_label=agent.full_name,
        details={"recipient_type": recipient_type},
    )
    return agent


async def review_requisites(
    session: AsyncSession,
    agent: Agent,
    *,
    new_status: str,
    actor: User,
    comment: str | None = None,
) -> Agent:
    if new_status not in ("accepted", "needs_fix", "empty"):
        _fail("INVALID_STATUS", "Недопустимый статус реквизитов")
    agent.requisites_status = new_status
    await session.flush()
    audit_log(
        action="agent_requisites_reviewed",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(agent.id),
        target_type="agent",
        target_label=new_status,
        details={"comment": comment},
    )
    return agent


# ---------------------------------------------------------------- админка


async def list_agents(session: AsyncSession, search: str | None = None) -> list[Agent]:
    query = select(Agent).order_by(Agent.created_at.desc())
    if search:
        needle = f"%{search.strip().lower()}%"
        query = query.where(
            func.lower(Agent.full_name).like(needle)
            | func.lower(Agent.code).like(needle)
            | func.lower(func.coalesce(Agent.company_name, "")).like(needle)
        )
    row = await session.execute(query)
    return list(row.scalars().all())


async def set_agent_status(
    session: AsyncSession, agent: Agent, *, active: bool, actor: User, reason: str | None = None
) -> Agent:
    agent.status = "active" if active else "blocked"
    agent.user.is_active = active
    await session.flush()
    audit_log(
        action="agent_status_changed",
        user_id=str(actor.id),
        actor_label=actor.email,
        target_id=str(agent.id),
        target_type="agent",
        target_label=agent.full_name,
        details={"active": active, "reason": reason},
    )
    return agent
