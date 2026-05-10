"""Celery tasks for feedback extraction.

Placeholder body — the real extraction flow lands in the next commit.
This skeleton just registers the task name on `celery_app` so the
worker boots with a known task surface.
"""

import logging

from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.feedback_tasks.extract_feedback_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def extract_feedback_task(self, feedback_id: int) -> dict:
    log.info(
        "extract_feedback_task_placeholder",
        extra={"feedback_id": feedback_id, "attempt": self.request.retries + 1},
    )
    return {"feedback_id": feedback_id, "status": "placeholder"}
