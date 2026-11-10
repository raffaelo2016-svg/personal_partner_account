import structlog
from sqlalchemy import func, select

from app.celery_app import celery
from app.config import settings
from app.models.task import Task
from app.services.task_service import _overdue_condition

logger = structlog.get_logger()


@celery.task(autoretry_for=(Exception,), max_retries=3, default_retry_delay=300)
def check_overdue_tasks():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        # Overdue is a deadline projection, not a lifecycle status: preserving
        # in_progress lets a later deadline extension restore the correct state.
        count = session.scalar(select(func.count()).select_from(Task).where(_overdue_condition())) or 0
        logger.info("overdue_tasks_checked", overdue=count)
    engine.dispose()
