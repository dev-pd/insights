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
    def __init__(
        self,
        repo: FeedbackRepository,
        llm_usage_repo: LlmUsageRepository,
    ):
        self.repo = repo
        self.llm_usage_repo = llm_usage_repo

    async def create_feedback(self, text: str) -> Feedback:
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

        # CRITICAL: commit BEFORE .delay() — worker queries the DB
        # immediately; uncommitted row → `not_found` → orphan PROCESSING. See CASE_STUDIES.md.
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
            # Second commit: first commit emptied the transaction.
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
