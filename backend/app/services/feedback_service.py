import logging
from typing import Literal

from app.constants import FeedbackStatus
from app.llm.validate import validate_feedback
from app.models.feedback import Feedback
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.tasks.feedback_tasks import extract_feedback_task

log = logging.getLogger(__name__)


class FeedbackService:
    """Orchestrates the validate → persist → dispatch flow.

    Phase 4: feedback rows are persisted with status=PROCESSING and the
    extraction happens in a Celery worker task. This service returns
    immediately; the SSE pipeline pushes status updates to the frontend
    as workers finish.

    The llm_usage_repo dependency is retained even though this service no
    longer writes usage rows directly — the dispatch boundary keeps the
    shape stable in case a future code path (sync fallback, eval harness)
    bypasses Celery and runs inline again.
    """

    def __init__(
        self,
        repo: FeedbackRepository,
        llm_usage_repo: LlmUsageRepository,
    ):
        self.repo = repo
        self.llm_usage_repo = llm_usage_repo

    async def create_feedback(self, text: str) -> Feedback:
        """Validate, persist as PROCESSING, dispatch extraction task. Returns
        immediately."""
        skip_reason = validate_feedback(text)
        if skip_reason is not None:
            log.info("feedback_skipped", extra={"skip_reason": skip_reason.value})
            return await self.repo.create(
                text=text,
                status=FeedbackStatus.SKIPPED,
                skip_reason=skip_reason,
            )

        feedback = await self.repo.create(
            text=text,
            status=FeedbackStatus.PROCESSING,
        )

        # CRITICAL: commit BEFORE dispatching the task. The worker picks up
        # tasks immediately and queries the DB for the feedback row; if the
        # request-end commit hasn't run yet, the worker sees `not_found`,
        # logs it, returns SUCCESS to Celery, and the row stays in
        # PROCESSING forever. We hit this exact race on a 20-item batch:
        # tasks for the first ~15 ids landed at the worker before the
        # request committed → 15 zombie rows.
        #
        # The session's request-end commit (in db.get_session) is still
        # safe — committing here just empties the current transaction;
        # the dependency's commit becomes a no-op.
        await self.repo.session.commit()

        try:
            extract_feedback_task.delay(feedback.id)
            log.info(
                "extraction_task_dispatched",
                extra={"feedback_id": feedback.id},
            )
        except Exception as error:  # noqa: BLE001 — broker outage path
            log.exception(
                "extraction_dispatch_failed",
                extra={"feedback_id": feedback.id, "error": str(error)},
            )
            feedback.status = FeedbackStatus.FAILED.value
            feedback.llm_metadata = {
                "error_type": type(error).__name__,
                "error": str(error),
                "context": "task_dispatch",
            }
            # We just committed, so we need another commit to persist the
            # FAILED flip. Without this, the row would stay PROCESSING
            # despite knowing the dispatch failed.
            await self.repo.session.commit()

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
        """Persist N rows as PROCESSING and dispatch N tasks.

        Workers process in parallel up to `celery_worker_concurrency` (default 4).
        Returns immediately — the frontend listens to SSE for status updates.
        """
        results: list[Feedback] = []
        total = len(texts)
        for index, text in enumerate(texts):
            try:
                feedback = await self.create_feedback(text)
                results.append(feedback)
                log.info(
                    "batch_item_dispatched",
                    extra={
                        "index": index,
                        "total": total,
                        "feedback_id": feedback.id,
                        "status": feedback.status,
                    },
                )
            except Exception as error:  # noqa: BLE001 — fault isolation per item
                log.exception(
                    "batch_item_create_failed",
                    extra={
                        "index": index,
                        "total": total,
                        "error_type": type(error).__name__,
                    },
                )
                continue
        return results
