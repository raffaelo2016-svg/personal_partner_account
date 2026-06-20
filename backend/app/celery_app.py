from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("partner_cabinet", broker=settings.REDIS_URL)

celery.autodiscover_tasks(["app.tasks"])

celery.conf.beat_schedule = {
    "check-overdue-tasks": {
        "task": "app.tasks.overdue_tasks.check_overdue_tasks",
        "schedule": crontab(hour=1, minute=0),
    },
    "check-overdue-court-fees": {
        "task": "app.tasks.overdue_fees.check_overdue_court_fees",
        "schedule": crontab(hour=1, minute=30),
    },
}
