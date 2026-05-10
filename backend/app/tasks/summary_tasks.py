"""Beat-scheduled task to keep the AI summary cache warm.

Runs every hour at the configured minute (see celery_app.beat_schedule).
By regenerating before the cache TTL expires, the dashboard never has a
cold-cache load — users always see an instant summary.

This is a cache-warming concern, not a correctness one. Failures don't
re-raise (next hour will retry naturally), so the task always returns
a result dict rather than raising.
"""

import asyncio
import logging

import redis.asyncio as redis_async

from app.core.config import get_settings
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.services.summary_service import SummaryService
from app.tasks._worker_session import worker_session_scope
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


async def _do_regenerate_summary() -> dict:
    settings = get_settings()
    redis_client = redis_async.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=5,
    )
    try:
        async with worker_session_scope() as session:
            feedback_repo = FeedbackRepository(session)
            usage_repo = LlmUsageRepository(session)
            service = SummaryService(feedback_repo, usage_repo, redis_client)
            # force_refresh=True deletes the existing cache key and regenerates
            # fresh. The service writes the new payload to Redis with the same
            # TTL as on-demand refreshes.
            result = await service.get_summary(force_refresh=True)
            await session.commit()
            return {
                "regenerated": True,
                "feedback_count": result.get("feedback_count", 0),
                "ts": result.get("generated_at"),
            }
    finally:
        await redis_client.aclose()


@celery_app.task(name="app.tasks.summary_tasks.regenerate_summary_task")
def regenerate_summary_task() -> dict:
    log.info("regenerate_summary_task_started")
    try:
        result = asyncio.run(_do_regenerate_summary())
        log.info("regenerate_summary_task_completed", extra=result)
        return result
    except Exception as error:  # noqa: BLE001 — beat will retry next hour
        log.exception(
            "regenerate_summary_task_failed",
            extra={"error_type": type(error).__name__, "error": str(error)},
        )
        return {"regenerated": False, "error": str(error)}
