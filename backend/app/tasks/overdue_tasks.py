import structlog
from sqlalchemy import update

from app.celery_app import celery
from app.config import settings
from app.core.time import moscow_today
from app.models.task import Task

logger = structlog.get_logger()


@celery.task(autoretry_for=(Exception,), max_retries=3, default_retry_delay=300)
def check_overdue_tasks():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        result = session.execute(
            update(Task)
            .where(Task.due_date < moscow_today(), Task.status.in_(["pending", "in_progress"]))
            .values(status="overdue")
            .returning(Task.id)
        )
        updated_ids = [str(row[0]) for row in result]
        session.commit()
        logger.info("overdue_tasks_checked", marked_overdue=len(updated_ids))
