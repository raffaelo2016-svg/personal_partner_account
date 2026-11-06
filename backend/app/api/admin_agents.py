"""API управления агентами для администраторов."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.models.agent import Agent, AgentAccrual, AgentPayoutRequest
from app.models.client import Client
from app.models.partner import Partner
from app.models.user import User
from app.schemas.agent import (
    AdminAgentDetail,
    AdminAgentRead,
    AgentAccrualRead,
    AgentPartner,
    AgentStats,
    AgentStatusUpdate,
    PartnerBindRequest,
    PayoutRead,
    PayoutStatusRequest,
    RequisitesReviewRequest,
)
from app.services import agent_service

logger = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin-agents"])


def _not_found(code: str = "AGENT_NOT_FOUND", message: str = "Агент не найден") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": code, "message": message},
    )


async def _agent_read(db: AsyncSession, agent: Agent) -> AdminAgentRead:
    stats = AgentStats(**await agent_service.agent_stats(db, agent.id))
    return AdminAgentRead(
        id=str(agent.id),
        email=agent.user.email,
        code=agent.code,
        full_name=agent.full_name,
        company_name=agent.company_name,
        status=agent.status,
        created_at=agent.created_at,
        requisites_status=agent.requisites_status,
        stats=stats,
    )


async def _partners_read(db: AsyncSession, agent_id) -> list[AgentPartner]:
    partners = await agent_service.list_agent_partners(db, agent_id)
    result: list[AgentPartner] = []
    for partner in partners:
        clients = (
            await db.execute(
                select(func.count(Client.id)).where(
                    Client.partner_id == partner.id, Client.deleted_at.is_(None)
                )
            )
        ).scalar_one()
        accrued = (
            await db.execute(
                select(func.coalesce(func.sum(AgentAccrual.amount), 0)).where(
                    AgentAccrual.partner_id == partner.id, AgentAccrual.status == "accrued"
                )
            )
        ).scalar_one()
        result.append(
            AgentPartner(
                id=str(partner.id),
                name=partner.company_name,
                status=partner.status,
                linked_at=partner.agent_linked_at,
                clients=int(clients),
                accrued=int(accrued),
            )
        )
    return result


def _accruals_read(accruals: list[AgentAccrual]) -> list[AgentAccrualRead]:
    return [
        AgentAccrualRead(
            id=str(a.id),
            client_ref=str(a.client_id)[:8],
            partner_name=a.partner.company_name if a.partner else "—",
            created_at=a.created_at,
            amount=a.amount,
            rate=a.rate,
            status=a.status,
            reason=a.reason,
        )
        for a in accruals
    ]


def _payouts_read(payouts: list[AgentPayoutRequest]) -> list[PayoutRead]:
    return [
        PayoutRead(
            id=str(p.id),
            amount=p.amount,
            status=p.status,
            period=p.period,
            created_at=p.created_at,
            paid_at=p.paid_at,
            comment=p.comment,
        )
        for p in payouts
    ]


async def _get_agent(db: AsyncSession, agent_id: str) -> Agent:
    import uuid as _uuid

    try:
        parsed = _uuid.UUID(agent_id)
    except ValueError as exc:
        raise _not_found() from exc
    agent = await db.get(Agent, parsed)
    if agent is None:
        raise _not_found()
    return agent


@router.get("/agents", response_model=list[AdminAgentRead])
async def list_agents(
    search: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("admin")),  # noqa: B008
):
    agents = await agent_service.list_agents(db, search=search)
    return [await _agent_read(db, agent) for agent in agents]


@router.get("/agents/{agent_id}", response_model=AdminAgentDetail)
async def agent_detail(
    agent_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("admin")),  # noqa: B008
):
    agent = await _get_agent(db, agent_id)
    accruals = await agent_service.list_accruals(db, agent.id)
    payouts = await agent_service.list_payouts(db, agent.id)
    return AdminAgentDetail(
        agent=await _agent_read(db, agent),
        partners=await _partners_read(db, agent.id),
        accruals=_accruals_read(accruals),
        payouts=_payouts_read(payouts),
    )


@router.patch("/agents/{agent_id}", response_model=AdminAgentRead)
async def change_agent_status(
    agent_id: str,
    body: AgentStatusUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("admin")),  # noqa: B008
):
    agent = await _get_agent(db, agent_id)
    await agent_service.set_agent_status(
        db, agent, active=body.is_active, actor=actor, reason=body.reason
    )
    await db.commit()
    return await _agent_read(db, agent)


@router.patch("/agents/{agent_id}/requisites", response_model=AdminAgentRead)
async def review_agent_requisites(
    agent_id: str,
    body: RequisitesReviewRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("admin")),  # noqa: B008
):
    agent = await _get_agent(db, agent_id)
    await agent_service.review_requisites(
        db, agent, new_status=body.status, actor=actor, comment=body.comment
    )
    await db.commit()
    return await _agent_read(db, agent)


@router.post("/partners/{partner_id}/agent", response_model=AdminAgentRead | None)
async def bind_partner(
    partner_id: str,
    body: PartnerBindRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("admin")),  # noqa: B008
):
    import uuid as _uuid

    try:
        partner_uuid = _uuid.UUID(partner_id)
    except ValueError as exc:
        raise _not_found("PARTNER_NOT_FOUND", "Партнёр не найден") from exc

    partner = await db.get(Partner, partner_uuid)
    if partner is None or partner.deleted_at is not None:
        raise _not_found("PARTNER_NOT_FOUND", "Партнёр не найден")

    agent = None
    if body.agent_id:
        agent = await _get_agent(db, body.agent_id)

    await agent_service.bind_partner_admin(
        db, partner, agent=agent, actor=actor, reason=body.reason, force=body.force
    )
    await db.commit()

    if agent is None:
        return None
    return await _agent_read(db, agent)


@router.get("/payouts", response_model=list[PayoutRead])
async def list_all_payouts(
    payout_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: User = Depends(require_role("admin")),  # noqa: B008
):
    query = select(AgentPayoutRequest).order_by(AgentPayoutRequest.created_at.desc())
    if payout_status:
        query = query.where(AgentPayoutRequest.status == payout_status)
    rows = await db.execute(query)
    return _payouts_read(list(rows.scalars().all()))


@router.patch("/payouts/{payout_id}", response_model=PayoutRead)
async def change_payout_status(
    payout_id: str,
    body: PayoutStatusRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    actor: User = Depends(require_role("admin")),  # noqa: B008
):
    import uuid as _uuid

    try:
        parsed = _uuid.UUID(payout_id)
    except ValueError as exc:
        raise _not_found("PAYOUT_NOT_FOUND", "Заявка не найдена") from exc

    request = await db.get(AgentPayoutRequest, parsed)
    if request is None:
        raise _not_found("PAYOUT_NOT_FOUND", "Заявка не найдена")

    await agent_service.update_payout_status(
        db, request, new_status=body.status, actor=actor, comment=body.comment
    )
    await db.commit()
    return _payouts_read([request])[0]
