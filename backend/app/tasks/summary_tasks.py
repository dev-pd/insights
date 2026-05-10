"""Celery tasks for AI summary regeneration (Beat-scheduled).

Placeholder body — the real cache-warming task lands in a later commit.
This skeleton registers the task so beat's schedule resolves on boot.
"""

import logging

from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.summary_tasks.regenerate_summary_task")
def regenerate_summary_task() -> dict:
    log.info("regenerate_summary_task_placeholder")
    return {"status": "placeholder"}
