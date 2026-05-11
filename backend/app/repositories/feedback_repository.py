from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Text, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FeedbackStatus, SkipReason
from app.models.feedback import Feedback


class FeedbackRepository:
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

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        sentiment: Literal["positive", "neutral", "negative"] | None = None,
        search: str | None = None,
    ) -> tuple[list[Feedback], int]:
        """Returns (items, total) where total reflects active filters so
        'Showing 1-20 of 47' stays correct under filtering. Search ILIKEs
        across text + JSONB themes/action_items (cast to Text — catches
        'any element contains substring' without array unnesting)."""
        base_stmt = select(Feedback)
        count_stmt = select(func.count(Feedback.id))

        if sentiment is not None:
            base_stmt = base_stmt.where(Feedback.sentiment == sentiment)
            count_stmt = count_stmt.where(Feedback.sentiment == sentiment)

        if search is not None and search.strip():
            pattern = f"%{search.strip()}%"
            search_filter = or_(
                Feedback.text.ilike(pattern),
                func.cast(Feedback.themes, Text).ilike(pattern),
                func.cast(Feedback.action_items, Text).ilike(pattern),
            )
            base_stmt = base_stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        items_stmt = (
            base_stmt.order_by(desc(Feedback.created_at)).offset(offset).limit(limit)
        )
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def get(self, feedback_id: int) -> Feedback | None:
        return await self.session.get(Feedback, feedback_id)

    async def list_recent_for_summary(
        self, cutoff: datetime, limit: int
    ) -> list[Feedback]:
        # EXTRACTED only — skipped/failed have no sentiment/themes to ground in.
        stmt = (
            select(Feedback)
            .where(Feedback.status == FeedbackStatus.EXTRACTED.value)
            .where(Feedback.created_at >= cutoff)
            .order_by(desc(Feedback.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_in_window(self, start: datetime, end: datetime) -> int:
        # Half-open [start, end) so back-to-back windows don't double-count.
        stmt = (
            select(func.count(Feedback.id))
            .where(Feedback.created_at >= start)
            .where(Feedback.created_at < end)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_by_status(self) -> dict[str, int]:
        stmt = select(Feedback.status, func.count(Feedback.id)).group_by(
            Feedback.status
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_total(self) -> int:
        stmt = select(func.count(Feedback.id))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def sentiment_counts(self) -> dict[str, int]:
        stmt = (
            select(Feedback.sentiment, func.count(Feedback.id))
            .where(Feedback.status == FeedbackStatus.EXTRACTED.value)
            .where(Feedback.sentiment.isnot(None))
            .group_by(Feedback.sentiment)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def all_themes_with_sentiment(
        self,
    ) -> list[tuple[list[str], str | None, datetime]]:
        # In-memory aggregation is fine at PoC scale. Production: materialized view.
        stmt = select(
            Feedback.themes, Feedback.sentiment, Feedback.created_at
        ).where(Feedback.status == FeedbackStatus.EXTRACTED.value)
        result = await self.session.execute(stmt)
        return [(row[0] or [], row[1], row[2]) for row in result.all()]

