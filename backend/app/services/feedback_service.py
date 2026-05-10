import logging
from typing import Literal

from app.constants import FeedbackStatus
from app.exceptions import LLMError
from app.llm.extract import extract_insights
from app.llm.validate import validate_feedback
from app.models.feedback import Feedback
from app.repositories.feedback_repository import FeedbackRepository

log = logging.getLogger(__name__)


class FeedbackService:
    """Orchestrates the validate → extract → persist flow.

    Phase 2: synchronous (POST blocks until LLM returns).
    Phase 4 will move extraction into a Celery task; this service is the
    dispatch boundary that won't change shape.
    """

    def __init__(self, repo: FeedbackRepository):
        self.repo = repo

    async def create_feedback(self, text: str) -> Feedback:
        # Step 1: pre-LLM validation. Cheap rejections never hit Anthropic.
        skip_reason = validate_feedback(text)
        if skip_reason is not None:
            log.info(
                "feedback_skipped",
                extra={"skip_reason": skip_reason.value},
            )
            return await self.repo.create(
                text=text,
                status=FeedbackStatus.SKIPPED,
                skip_reason=skip_reason,
            )

        # Step 2: LLM extraction. Wrapper handles retries; LLMError on terminal.
        try:
            result, metadata = await extract_insights(text)
        except LLMError as e:
            log.error(
                "feedback_extraction_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return await self.repo.create(
                text=text,
                status=FeedbackStatus.FAILED,
                llm_metadata={"error_type": type(e).__name__, "error": str(e)},
            )

        # Step 3: persist with extracted insights.
        return await self.repo.create(
            text=text,
            status=FeedbackStatus.EXTRACTED,
            sentiment=result.sentiment,
            themes=result.themes,
            action_items=result.action_items,
            language=result.language,
            llm_metadata=metadata,
        )

    async def list_recent(self, limit: int) -> list[Feedback]:
        return await self.repo.list_recent(limit=limit)

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        sentiment: Literal["positive", "neutral", "negative"] | None = None,
    ) -> tuple[list[Feedback], int]:
        return await self.repo.list_paginated(
            offset=offset, limit=limit, sentiment=sentiment
        )
