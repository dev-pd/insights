"""Celery tasks for feedback extraction.

The Celery task body runs in sync context; the actual extraction +
DB-update + pub/sub flow is async. We bridge with `asyncio.run` per task,
which spins up a fresh event loop, runs the body, and tears it down on
return. For PoC scale that's fine; production with very high throughput
might prefer a long-lived loop per worker (via `celery.signals`), but
that's a graduation concern.
"""

import asyncio
import logging

import redis as redis_sync

from app.constants import FeedbackStatus, LlmCallType
from app.core.config import get_settings
from app.events.pubsub import (
    publish_feedback_event_sync,
    publish_stats_invalidation_sync,
)
from app.exceptions import LLMError
from app.llm.extract import extract_insights
from app.models.feedback import Feedback
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.tasks._worker_session import get_worker_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


def _sync_redis_client() -> redis_sync.Redis:
    """Sync Redis client for fire-and-forget publishes from worker context."""
    settings = get_settings()
    return redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)


async def _do_extraction(feedback_id: int) -> dict:
    """Async core: load row, call Anthropic, update row, publish events."""
    session_factory = get_worker_session_factory()
    redis_client = _sync_redis_client()

    async with session_factory() as session:
        feedback = await session.get(Feedback, feedback_id)
        if feedback is None:
            log.error(
                "feedback_not_found_for_extraction",
                extra={"feedback_id": feedback_id},
            )
            return {"feedback_id": feedback_id, "status": "not_found"}

        if feedback.status != FeedbackStatus.PROCESSING.value:
            # Already processed (retry of a task whose first attempt succeeded
            # after the broker thought it died, or someone manually changed
            # status). Don't re-run extraction.
            log.warning(
                "feedback_not_in_processing_status",
                extra={
                    "feedback_id": feedback_id,
                    "status": feedback.status,
                },
            )
            return {
                "feedback_id": feedback_id,
                "status": "skipped_wrong_state",
            }

        try:
            result, metadata = await extract_insights(feedback.text)
        except LLMError as error:
            log.error(
                "extraction_failed",
                extra={
                    "feedback_id": feedback_id,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
            feedback.status = FeedbackStatus.FAILED.value
            feedback.llm_metadata = {
                "error_type": type(error).__name__,
                "error": str(error),
                "context": "celery_task",
            }
            await session.commit()

            publish_feedback_event_sync(
                redis_client,
                feedback_id=feedback_id,
                status=FeedbackStatus.FAILED.value,
                payload={"error": str(error)},
            )
            publish_stats_invalidation_sync(redis_client)

            # Re-raise so Celery's autoretry can kick in (LLMError is in
            # autoretry_for). If retries are exhausted, the row stays FAILED.
            raise

        feedback.status = FeedbackStatus.EXTRACTED.value
        feedback.sentiment = result.sentiment
        feedback.themes = result.themes
        feedback.action_items = result.action_items
        feedback.language = result.language
        feedback.llm_metadata = metadata

        usage_repo = LlmUsageRepository(session)
        await usage_repo.record(
            call_type=LlmCallType.EXTRACTION.value,
            model=metadata.get("model", "unknown"),
            input_tokens=metadata.get("input_tokens", 0),
            output_tokens=metadata.get("output_tokens", 0),
            latency_ms=metadata.get("latency_ms"),
            prompt_version=metadata.get("prompt_version"),
            feedback_id=feedback.id,
        )

        await session.commit()

        publish_feedback_event_sync(
            redis_client,
            feedback_id=feedback_id,
            status=FeedbackStatus.EXTRACTED.value,
            payload={
                "sentiment": result.sentiment,
                "themes": result.themes,
                "action_items": result.action_items,
                "language": result.language,
            },
        )
        publish_stats_invalidation_sync(redis_client)

        return {
            "feedback_id": feedback_id,
            "status": FeedbackStatus.EXTRACTED.value,
            "sentiment": result.sentiment,
            "input_tokens": metadata.get("input_tokens"),
            "output_tokens": metadata.get("output_tokens"),
        }


@celery_app.task(
    name="app.tasks.feedback_tasks.extract_feedback_task",
    bind=True,
    # Retry only on transient errors. Validation errors / 4xx responses are
    # our bug and shouldn't waste retry budget.
    autoretry_for=(LLMError, TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def extract_feedback_task(self, feedback_id: int) -> dict:
    """Celery entry point. Bridges sync → async via asyncio.run."""
    log.info(
        "extract_feedback_task_started",
        extra={"feedback_id": feedback_id, "attempt": self.request.retries + 1},
    )
    try:
        return asyncio.run(_do_extraction(feedback_id))
    except Exception as error:
        log.error(
            "extract_feedback_task_failed",
            extra={
                "feedback_id": feedback_id,
                "attempt": self.request.retries + 1,
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise
