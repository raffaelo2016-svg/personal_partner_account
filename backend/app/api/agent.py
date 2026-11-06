"""API агентского кабинета."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import require_role
from app.database import get_db
from app.models.agent import Agent, AgentAccrual
from app.models.client import Client
from app.models.user import User
from app.schemas.agent import (
    AgentAccrualRead,
    AgentMe,
    AgentPartner,
    AgentProfile,
    AgentStats,
    PayoutRead,
    RequisitesUpdate,
)
from app.services import agent_service

logger = structlog.get_logger()

router = APIRouter(prefix="/agent", tags=["agent"])


async def get_current_agent(
    user: User = Depends(require_role("agent")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Agent:
    agent = await agent_service.get_agent_by_user(db, user.id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AGENT_NOT_FOUND", "message": "Профиль агента не найден"},
        )
    return agent


def _profile(agent: Agent) -> AgentProfile:
    base = settings.PUBLIC_APP_URL.rstrip("/")
    return AgentProfile(
        id=str(agent.id),
        code=agent.code,
        full_name=agent.full_name,
        phone=agent.phone,
        company_name=agent.company_name,
        status=agent.status,
        requisites_status=agent.requisites_status,
        requisites_recipient_type=agent.requisites_recipient_type,
        referral_link=f"{base}/register?agent={agent.code}",
    )


async def _stats(db: AsyncSession, agent_id) -> AgentStats:
    return AgentStats(**await agent_service.agent_stats(db, agent_id))


@router.get("/me", response_model=AgentMe)
async def agent_me(
    agent: Agent = Depends(get_current_agent),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return AgentMe(profile=_profile(agent), stats=await _stats(db, agent.id))


@router.get("/partners", response_model=list[AgentPartner])
async def agent_partners(
    agent: Agent = Depends(get_current_agent),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    partners = await agent_service.list_agent_partners(db, agent.id)
    result: list[AgentPartner] = []
    for partner in partners:
        clients = (
            await db.execute(
                select(func.count(Client.id)).where(Client.partner_id == partner.id, Client.deleted_at.is_(None))
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


@router.get("/accruals", response_model=list[AgentAccrualRead])
async def agent_accruals(
    agent: Agent = Depends(get_current_agent),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    accruals = await agent_service.list_accruals(db, agent.id)
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
            comment=a.comment,
        )
        for a in accruals
    ]


@router.get("/payouts", response_model=list[PayoutRead])
async def agent_payouts(
    agent: Agent = Depends(get_current_agent),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    payouts = await agent_service.list_payouts(db, agent.id)
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


@router.post("/payouts", response_model=PayoutRead, status_code=201)
async def create_payout(
    agent: Agent = Depends(get_current_agent),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    request = await agent_service.create_payout_request(db, agent)
    await db.commit()
    return PayoutRead(
        id=str(request.id),
        amount=request.amount,
        status=request.status,
        period=request.period,
        created_at=request.created_at,
        paid_at=request.paid_at,
        comment=request.comment,
    )


@router.put("/requisites", response_model=AgentProfile)
async def update_requisites(
    body: RequisitesUpdate,
    agent: Agent = Depends(get_current_agent),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    updated = await agent_service.save_requisites(db, agent, recipient_type=body.recipient_type, data=body.data)
    await db.commit()
    return _profile(updated)
