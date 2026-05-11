"""Generates/caches the dashboard AI summary. Single Redis key with TTL;
failures are not cached (would lock the dashboard into 'broken' for a full
TTL when Anthropic has a bad minute)."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis_async

from app.constants import LlmCallType
from app.core.config import get_settings
from app.exceptions import LLMError
from app.llm.summarize import generate_summary
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.llm_usage_repository import LlmUsageRepository

log = logging.getLogger(__name__)

SUMMARY_CACHE_KEY = "summary:current"


class SummaryService:
    def __init__(
        self,
        repo: FeedbackRepository,
        llm_usage_repo: LlmUsageRepository,
        redis_client: redis_async.Redis,
    ):
        self.repo = repo
        self.llm_usage_repo = llm_usage_repo
        self.redis = redis_client

    async def get_summary(self, force_refresh: bool = False) -> dict[str, Any]:
        if force_refresh:
            await self.redis.delete(SUMMARY_CACHE_KEY)
        else:
            cached_raw = await self.redis.get(SUMMARY_CACHE_KEY)
            if cached_raw is not None:
                cached_data = json.loads(cached_raw)
                cached_data["cached"] = True
                return cached_data

        return await self._generate_and_cache()

    async def _generate_and_cache(self) -> dict[str, Any]:
        settings = get_settings()
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=settings.summary_lookback_hours
        )
        recent = await self.repo.list_recent_for_summary(
            cutoff=cutoff, limit=settings.summary_max_feedback_items
        )

        feedback_items = [
            {
                "text": feedback.text,
                "sentiment": feedback.sentiment,
                "themes": feedback.themes or [],
                "action_items": feedback.action_items or [],
            }
            for feedback in recent
        ]

        try:
            summary_text, metadata = await generate_summary(feedback_items)
        except LLMError as error:
            log.exception(
                "summary_generation_failed",
                extra={
                    "error_type": type(error).__name__,
                    "feedback_count": len(feedback_items),
                },
            )
            return {
                "text": "Summary temporarily unavailable. Try refreshing in a moment.",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "feedback_count": len(feedback_items),
                "cached": False,
                "error": str(error),  # error path NOT cached — next request retries
                "metadata": None,
            }

        # input_tokens=0 is the "not enough data" sentinel — no call made, don't record.
        if metadata.get("input_tokens", 0) > 0:
            await self.llm_usage_repo.record(
                call_type=LlmCallType.SUMMARY.value,
                model=metadata.get("model", "unknown"),
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                latency_ms=metadata.get("latency_ms"),
                prompt_version=metadata.get("prompt_version"),
                feedback_id=None,
            )

        result: dict[str, Any] = {
            "text": summary_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feedback_count": len(feedback_items),
            "cached": False,
            "error": None,
            "metadata": metadata,
        }

        # input_tokens == 0 is the "not enough feedback yet" sentinel from
        # summarize.py — no LLM call was made. Caching it would freeze the
        # placeholder text in place until TTL/invalidator fires, even after
        # the cohort grows past the min threshold. Skip the SET so the next
        # read re-evaluates the cohort.
        if metadata.get("input_tokens", 0) > 0:
            await self.redis.setex(
                SUMMARY_CACHE_KEY,
                settings.summary_cache_ttl_seconds,
                json.dumps(result),
            )
        return result
