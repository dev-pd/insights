"""Celery application configuration.

Centralizes all Celery-wide settings so individual task modules just
register handlers on `celery_app` and don't repeat config.
"""

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
    # Ack after task body returns, not on prefetch — failures requeue.
    task_acks_late=True,
    # If a worker dies mid-task, the broker requeues for another worker.
    task_reject_on_worker_lost=True,
    # One task at a time per worker process — avoid hoarding tasks that
    # other workers could be running in parallel.
    worker_prefetch_multiplier=1,
    # Results auto-expire so the result backend doesn't grow unbounded.
    result_expires=settings.celery_result_expires_seconds,
    # JSON only — never accept pickle from an untrusted broker.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # SIGTERM-then-SIGKILL window. Tasks get soft_time_limit seconds for
    # graceful shutdown (cleaning up DB sessions etc), then hard kill.
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
    task_time_limit=settings.celery_task_time_limit_seconds,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "regenerate-summary-hourly": {
            "task": "app.tasks.summary_tasks.regenerate_summary_task",
            # Every hour at the configured minute (default :00).
            "schedule": crontab(minute=settings.celery_beat_summary_cron_minute),
        },
    },
)
