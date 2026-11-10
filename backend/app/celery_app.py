from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery(
    "partner_cabinet",
    broker=settings.REDIS_URL,
    include=[
        "app.tasks.bitrix24_sync",
        "app.tasks.overdue_fees",
        "app.tasks.overdue_tasks",
    ],
)
celery.conf.task_acks_late = True
celery.conf.task_reject_on_worker_lost = True

celery.conf.beat_schedule = {
    "check-overdue-tasks": {
        "task": "app.tasks.overdue_tasks.check_overdue_tasks",
        "schedule": crontab(hour=1, minute=0),
    },
    "check-overdue-court-fees": {
        "task": "app.tasks.overdue_fees.check_overdue_court_fees",
        "schedule": crontab(hour=1, minute=30),
    },
    "process-bitrix24-outbox": {
        "task": "app.tasks.bitrix24_sync.process_bitrix_outbox",
        "schedule": 15.0,
    },
    "poll-bitrix24-chat-events": {
        "task": "app.tasks.bitrix24_sync.poll_bitrix_chat_events",
        "schedule": 15.0,
    },
    "reconcile-bitrix24-chat-files": {
        "task": "app.tasks.bitrix24_sync.reconcile_bitrix_chat_files",
        "schedule": 60.0,
    },
    "reconcile-bitrix24-sync": {
        "task": "app.tasks.bitrix24_sync.reconcile_bitrix_sync",
        "schedule": crontab(minute="*/5"),
    },
    "discover-bitrix24-partner-tasks": {
        "task": "app.tasks.bitrix24_sync.discover_bitrix_partner_tasks",
        "schedule": 60.0,
    },
}
