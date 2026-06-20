from datetime import date

import structlog
from sqlalchemy import update

from app.celery_app import celery
from app.config import settings
from app.models.court_fee import CourtFee

logger = structlog.get_logger()


@celery.task(autoretry_for=(Exception,), max_retries=3, default_retry_delay=300)
def check_overdue_court_fees():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        result = session.execute(
            update(CourtFee)
            .where(
                CourtFee.due_date < date.today(),
                CourtFee.status == "unpaid",
                CourtFee.deleted_at.is_(None),
            )
            .values(status="overdue")
            .returning(CourtFee.id)
        )
        updated_ids = [str(row[0]) for row in result]
        session.commit()
        logger.info("overdue_court_fees_checked", marked_overdue=len(updated_ids))
