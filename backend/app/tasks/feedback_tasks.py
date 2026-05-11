"""Celery tasks for feedback extraction.

Sync Celery body bridges to async via `asyncio.run` per task — fresh loop
per invocation. See `client.py:get_client()` for why caching across loops
requires object-identity comparison.
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
from app.tasks._worker_session import worker_session_scope
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)

# Resolved at import — Celery decorator args can't be late-bound.
_retry_settings = get_settings()


def _sync_redis_client() -> redis_sync.Redis:
    settings = get_settings()
    return redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)


async def _mark_failed(
    session,
    redis_client: redis_sync.Redis,
    feedback: Feedback,
    error: Exception,
    context: str,
) -> None:
    """Centralized FAILED transition + event publish. Both the LLMError path
    (re-raised for autoretry) and the broad-catch path (re-raised for Celery
    FAILURE) must go through here — direct row updates would risk skipping
    the pub/sub notify."""
    log.exception(
        "extraction_failed",
        extra={
            "feedback_id": feedback.id,
            "error_type": type(error).__name__,
            "context": context,
        },
    )
    feedback.status = FeedbackStatus.FAILED.value
    feedback.llm_metadata = {
        "error_type": type(error).__name__,
        "error": str(error),
        "context": context,
    }
    await session.commit()

    publish_feedback_event_sync(
        redis_client,
        feedback_id=feedback.id,
        status=FeedbackStatus.FAILED.value,
        payload={"error": str(error)},
    )
    publish_stats_invalidation_sync(redis_client)


async def _do_extraction(feedback_id: int) -> dict:
    redis_client = _sync_redis_client()

    async with worker_session_scope() as session:
        feedback = await session.get(Feedback, feedback_id)
        if feedback is None:
            log.error(
                "feedback_not_found_for_extraction",
                extra={"feedback_id": feedback_id},
            )
            return {"feedback_id": feedback_id, "status": "not_found"}

        if feedback.status != FeedbackStatus.PROCESSING.value:
            # Retry of a task whose first attempt already succeeded, or
            # manual state edit. Don't re-extract.
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
            # Re-raise so autoretry can pick it up.
            await _mark_failed(
                session,
                redis_client,
                feedback,
                error,
                context="celery_task_llm_error",
            )
            raise
        except Exception as error:  # noqa: BLE001
            # Without this catch, an uncaught exception leaves the row in
            # PROCESSING forever (orphan-row bug). Mark FAILED, then re-raise
            # — Exception is NOT in autoretry_for, so this surfaces as a
            # permanent Celery failure, which is correct for our bugs
            # (AttributeError, KeyError, etc.).
            await _mark_failed(
                session,
                redis_client,
                feedback,
                error,
                context="celery_task_uncaught",
            )
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
    # Transient errors only. 4xx is our bug and shouldn't burn retry budget.
    # Settings defaults (6/120s) absorb multi-minute 429 bursts in practice.
    autoretry_for=(LLMError, TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=_retry_settings.celery_extract_retry_backoff_max,
    retry_jitter=True,
    max_retries=_retry_settings.celery_extract_max_retries,
)
def extract_feedback_task(self, feedback_id: int) -> dict:
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
