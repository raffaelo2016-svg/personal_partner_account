from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.client import Client
from app.models.user import User
from app.services.client_service import COMPLETED_STATUSES, _get_partner_id_for_user
from app.services.task_service import get_task_stats, get_urgent_tasks

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def partner_dashboard(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    partner_id = await _get_partner_id_for_user(db, str(current_user.id))

    base_clients = select(func.count()).where(
        Client.deleted_at.is_(None),
        Client.partner_id == partner_id,
    )
    total_clients = (await db.execute(base_clients)).scalar() or 0
    before_court = (await db.execute(base_clients.where(Client.type == "before_court"))).scalar() or 0
    in_court = (await db.execute(base_clients.where(Client.type == "in_court"))).scalar() or 0
    completed = (await db.execute(base_clients.where(Client.status.in_(COMPLETED_STATUSES)))).scalar() or 0
    new_this_week = (
        await db.execute(base_clients.where(Client.created_at >= func.now() - text("interval '7 days'")))
    ).scalar() or 0

    task_stats = await get_task_stats(db, partner_id=str(partner_id))
    total_tasks = task_stats.total
    completed_tasks = task_stats.completed
    task_pct = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    urgent_rows = await get_urgent_tasks(db, partner_id=str(partner_id), priority="high")
    urgent_tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "client_id": t.client_id,
            "client_name": t.client_name,
        }
        for t in urgent_rows
    ]

    recent_q = (
        select(Client)
        .where(Client.deleted_at.is_(None), Client.partner_id == partner_id)
        .order_by(Client.created_at.desc())
        .limit(5)
    )
    recent_rows = (await db.execute(recent_q)).scalars().all()
    recent_clients = [
        {
            "id": str(c.id),
            "full_name": c.full_name,
            "type": c.type,
            "status": c.status,
            "created_at": str(c.created_at),
        }
        for c in recent_rows
    ]

    return {
        "stats": {
            "total_clients": total_clients,
            "new_this_week": new_this_week,
            "before_court": before_court,
            "in_court": in_court,
            "completed": completed,
        },
        "urgent_tasks": urgent_tasks,
        "task_completion": {
            "percent": task_pct,
            "total": total_tasks,
            "completed": completed_tasks,
        },
        "recent_clients": recent_clients,
    }
