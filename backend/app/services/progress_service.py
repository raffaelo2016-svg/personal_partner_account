from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.client import Client
from app.models.client_status_log import ClientStatusLog
from app.models.enums import ClientStatus

StageDict = dict[str, Any]

STAGES: list[StageDict] = [
    {
        "id": 1,
        "title": "Сбор документов",
        "status_key": ClientStatus.DOCUMENTS_COLLECTION,
    },
    {
        "id": 2,
        "title": "Формирование документов",
        "status_key": ClientStatus.DOCUMENTS_FORMATION,
    },
    {
        "id": 3,
        "title": "Отправка в суд",
        "status_key": ClientStatus.SENT_TO_COURT,
    },
    {
        "id": 4,
        "title": "Документы приняты / не приняты",
        "status_key": ClientStatus.DOCUMENTS_DECISION,
    },
    {
        "id": 5,
        "title": "Ожидание заседания",
        "status_key": ClientStatus.WAITING_HEARING,
    },
    {
        "id": 6,
        "title": "Реструктуризация",
        "status_key": ClientStatus.RESTRUCTURING,
    },
    {
        "id": 7,
        "title": "Торги",
        "status_key": ClientStatus.AUCTION,
    },
    {
        "id": 8,
        "title": "Реализация",
        "status_key": ClientStatus.REALIZATION,
    },
]

LINEAR_STATUS_ORDER: list[ClientStatus] = [
    ClientStatus.DOCUMENTS_COLLECTION,
    ClientStatus.DOCUMENTS_FORMATION,
    ClientStatus.SENT_TO_COURT,
    ClientStatus.DOCUMENTS_DECISION,
    ClientStatus.WAITING_HEARING,
    ClientStatus.RESTRUCTURING,
    ClientStatus.AUCTION,
    ClientStatus.REALIZATION,
    ClientStatus.COMPLETED,
]


def _get_status_index(status_str: str) -> int:
    try:
        s = ClientStatus(status_str)
        if s in LINEAR_STATUS_ORDER:
            return LINEAR_STATUS_ORDER.index(s)
    except ValueError:
        pass
    return -1


async def get_progress(
    session: AsyncSession,
    client_id: str,
    *,
    partner_id: str | None = None,
) -> dict:
    client = await session.get(Client, client_id)
    if not client or client.deleted_at is not None:
        raise NotFound("Client not found")
    if partner_id and str(client.partner_id) != partner_id:
        raise NotFound("Client not found")

    current_index = _get_status_index(client.status)

    logs_result = await session.execute(
        select(ClientStatusLog.to_status, ClientStatusLog.changed_at)
        .where(ClientStatusLog.client_id == client_id)
        .order_by(ClientStatusLog.changed_at)
    )
    completed_statuses: dict[str, str] = {}
    for row in logs_result:
        completed_statuses[row.to_status] = str(row.changed_at) if row.changed_at else ""

    total_stages = len(STAGES)
    completed_count = 0
    stages_output = []

    for stage in STAGES:
        stage_index = _get_status_index(stage["status_key"].value)
        if stage_index < current_index:
            stage_status = "completed"
            completed_count += 1
        elif stage_index == current_index:
            stage_status = "in_progress"
        else:
            stage_status = "pending"

        stages_output.append(
            {
                "id": stage["id"],
                "title": stage["title"],
                "status": stage_status,
                "completed_at": completed_statuses.get(stage["status_key"].value),
            }
        )

    overall_percent = round((completed_count / total_stages) * 100) if total_stages > 0 else 0

    return {
        "overall_percent": overall_percent,
        "current_status": client.status,
        "stages": stages_output,
    }
