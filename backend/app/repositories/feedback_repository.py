from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FeedbackStatus, SkipReason
from app.models.feedback import Feedback


class FeedbackRepository:
    """Data access for Feedback. The only place SQLAlchemy queries live for this entity."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        text: str,
        status: FeedbackStatus,
        sentiment: str | None = None,
        themes: list[str] | None = None,
        action_items: list[str] | None = None,
        language: str | None = None,
        skip_reason: SkipReason | None = None,
        llm_metadata: dict[str, Any] | None = None,
    ) -> Feedback:
        feedback = Feedback(
            text=text,
            status=status.value,
            sentiment=sentiment,
            themes=themes if themes is not None else [],
            action_items=action_items if action_items is not None else [],
            language=language,
            skip_reason=skip_reason.value if skip_reason is not None else None,
            llm_metadata=llm_metadata,
        )
        self.session.add(feedback)
        await self.session.flush()
        await self.session.refresh(feedback)
        return feedback

    async def list_recent(self, limit: int) -> list[Feedback]:
        stmt = select(Feedback).order_by(desc(Feedback.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, feedback_id: int) -> Feedback | None:
        return await self.session.get(Feedback, feedback_id)
