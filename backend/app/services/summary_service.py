"""Summary service — generates and caches the dashboard AI summary.

Cache strategy: a single Redis key ("summary:current") with the configured
TTL. On cache miss we generate fresh and write back. Manual refresh forces
regeneration by deleting the key first. We never cache LLM failures —
caching a failure for an hour would lock the dashboard into "broken" until
the TTL elapsed.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis_async

from app.core.config import get_settings
from app.exceptions import LLMError
from app.llm.summarize import generate_summary
from app.repositories.feedback_repository import FeedbackRepository

log = logging.getLogger(__name__)

# Identifier, not a tunable — staying as a module constant.
SUMMARY_CACHE_KEY = "summary:current"


class SummaryService:
    def __init__(self, repo: FeedbackRepository, redis_client: redis_async.Redis):
        self.repo = repo
        self.redis = redis_client

    async def get_summary(self, force_refresh: bool = False) -> dict[str, Any]:
        """Return the current summary, generating fresh if cache is empty
        or `force_refresh` is True.

        Shape: {text, generated_at, feedback_count, cached, error?, metadata?}.
        """
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
            # Don't cache failures — next request will retry, which is what
            # we want when Anthropic is having a bad minute.
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
                "error": str(error),
                "metadata": None,
            }

        result: dict[str, Any] = {
            "text": summary_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feedback_count": len(feedback_items),
            "cached": False,
            "error": None,
            "metadata": metadata,
        }

        await self.redis.setex(
            SUMMARY_CACHE_KEY,
            settings.summary_cache_ttl_seconds,
            json.dumps(result),
        )
        return result
