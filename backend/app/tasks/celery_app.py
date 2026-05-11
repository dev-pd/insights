from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "insights",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.feedback_tasks",
        "app.tasks.summary_tasks",
    ],
)

celery_app.conf.update(
    # Late ack + reject-on-lost: crashed workers requeue mid-task.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # One in-flight task per fork; prevents one worker hoarding the queue.
    worker_prefetch_multiplier=1,
    result_expires=settings.celery_result_expires_seconds,
    task_serializer="json",  # never pickle from an untrusted broker
    result_serializer="json",
    accept_content=["json"],
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,  # graceful cleanup
    task_time_limit=settings.celery_task_time_limit_seconds,  # SIGKILL
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "regenerate-summary-hourly": {
            "task": "app.tasks.summary_tasks.regenerate_summary_task",
            "schedule": crontab(minute=settings.celery_beat_summary_cron_minute),
        },
    },
)
