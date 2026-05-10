from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FeedbackStatus
from app.models.feedback import Feedback


class FeedbackRepository:
    """Data access for the Feedback entity. Phase 1 stubs only."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, feedback_id: UUID) -> Feedback | None:
        raise NotImplementedError("Implemented in Phase 2")

    async def list_recent(
        self,
        query: str | None = None,
        limit: int = 100,
    ) -> list[Feedback]:
        raise NotImplementedError("Implemented in Phase 2")

    async def create(
        self,
        text: str,
        status: FeedbackStatus,
        skip_reason: str | None = None,
    ) -> Feedback:
        raise NotImplementedError("Implemented in Phase 2")

    async def update_extraction(
        self,
        feedback_id: UUID,
        sentiment: str,
        themes: list[str],
        action_items: list[str],
        language: str,
    ) -> None:
        raise NotImplementedError("Implemented in Phase 2")

    async def mark_failed(self, feedback_id: UUID, reason: str) -> None:
        raise NotImplementedError("Implemented in Phase 2")
