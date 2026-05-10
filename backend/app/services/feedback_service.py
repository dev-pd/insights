import logging
from typing import Literal

from app.constants import FeedbackStatus, LlmCallType
from app.exceptions import LLMError
from app.llm.extract import extract_insights
from app.llm.validate import validate_feedback
from app.models.feedback import Feedback
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.llm_usage_repository import LlmUsageRepository

log = logging.getLogger(__name__)


class FeedbackService:
    """Orchestrates the validate → extract → persist flow.

    Phase 2: synchronous (POST blocks until LLM returns).
    Phase 4 will move extraction into a Celery task; this service is the
    dispatch boundary that won't change shape.
    """

    def __init__(
        self,
        repo: FeedbackRepository,
        llm_usage_repo: LlmUsageRepository,
    ):
        self.repo = repo
        self.llm_usage_repo = llm_usage_repo

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
        except LLMError as error:
            log.error(
                "feedback_extraction_failed",
                extra={"error_type": type(error).__name__, "error": str(error)},
            )
            return await self.repo.create(
                text=text,
                status=FeedbackStatus.FAILED,
                llm_metadata={
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )

        # Step 3: persist with extracted insights.
        feedback = await self.repo.create(
            text=text,
            status=FeedbackStatus.EXTRACTED,
            sentiment=result.sentiment,
            themes=result.themes,
            action_items=result.action_items,
            language=result.language,
            llm_metadata=metadata,
        )

        # Step 4: record LLM usage. Done after persistence so we have feedback.id
        # for the FK. The shared session means both writes commit together; if
        # the request later fails, both rows roll back atomically.
        await self.llm_usage_repo.record(
            call_type=LlmCallType.EXTRACTION.value,
            model=metadata.get("model", "unknown"),
            input_tokens=metadata.get("input_tokens", 0),
            output_tokens=metadata.get("output_tokens", 0),
            latency_ms=metadata.get("latency_ms"),
            prompt_version=metadata.get("prompt_version"),
            feedback_id=feedback.id,
        )

        return feedback

    async def list_recent(self, limit: int) -> list[Feedback]:
        return await self.repo.list_recent(limit=limit)

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        sentiment: Literal["positive", "neutral", "negative"] | None = None,
        search: str | None = None,
    ) -> tuple[list[Feedback], int]:
        return await self.repo.list_paginated(
            offset=offset, limit=limit, sentiment=sentiment, search=search
        )

    async def create_feedback_batch(self, texts: list[str]) -> list[Feedback]:
        """Process a batch of feedback texts sequentially.

        Sequential — not asyncio.gather — for two reasons:
          1. Anthropic rate limits (RPM/TPM) bite quickly on parallel batches.
          2. The shared async session doesn't tolerate concurrent commits well;
             one rolled-back transaction would poison the others.

        Per-item failures are isolated: any unexpected exception during a single
        item gets caught, logged, and persisted as a FAILED row so the user sees
        what happened rather than a silent drop. The whole batch keeps moving.

        Phase 4 graduation: each text dispatches as its own Celery task and the
        UI reads status updates over SSE. This sync method is the dispatch
        boundary that won't change shape — only its body.
        """
        results: list[Feedback] = []
        total = len(texts)
        for index, text in enumerate(texts):
            try:
                feedback = await self.create_feedback(text)
                results.append(feedback)
                log.info(
                    "batch_item_processed",
                    extra={"index": index, "total": total, "status": feedback.status},
                )
            except Exception as error:  # noqa: BLE001 — fault isolation per item
                log.exception(
                    "batch_item_failed",
                    extra={
                        "index": index,
                        "total": total,
                        "error_type": type(error).__name__,
                    },
                )
                failed_row = await self.repo.create(
                    text=text,
                    status=FeedbackStatus.FAILED,
                    llm_metadata={
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "context": "batch_processing",
                    },
                )
                results.append(failed_row)
        return results
