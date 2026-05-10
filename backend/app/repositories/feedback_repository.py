from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Float, Integer, desc, func, select
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

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        sentiment: Literal["positive", "neutral", "negative"] | None = None,
    ) -> tuple[list[Feedback], int]:
        """Page of feedback plus total matching count for the pagination UI.

        The total reflects the active filter, not the table size — so "Showing
        1-20 of 47" stays accurate when a sentiment filter is on.
        """
        base_stmt = select(Feedback)
        count_stmt = select(func.count(Feedback.id))

        if sentiment is not None:
            base_stmt = base_stmt.where(Feedback.sentiment == sentiment)
            count_stmt = count_stmt.where(Feedback.sentiment == sentiment)

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

    async def count_in_window(self, start: datetime, end: datetime) -> int:
        """Count feedback created in [start, end). Half-open so back-to-back
        windows don't double-count the boundary instant."""
        stmt = (
            select(func.count(Feedback.id))
            .where(Feedback.created_at >= start)
            .where(Feedback.created_at < end)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # ── Stats aggregation queries ───────────────────────────────────────────

    async def count_by_status(self) -> dict[str, int]:
        """Count of feedback rows grouped by status string."""
        stmt = select(Feedback.status, func.count(Feedback.id)).group_by(
            Feedback.status
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_total(self) -> int:
        """Total feedback rows across all statuses."""
        stmt = select(func.count(Feedback.id))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def sentiment_counts(self) -> dict[str, int]:
        """Count of extracted feedback grouped by sentiment string."""
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
        """Return (themes, sentiment, created_at) for all extracted feedback.

        Used for in-memory aggregation of top themes and sentiment-over-time.
        For PoC scale (a few thousand rows) in-memory aggregation is fine and
        avoids a denormalized themes table. Production scale would replace
        with a materialized view; documented in NOTES.md graduation path.
        """
        stmt = select(
            Feedback.themes, Feedback.sentiment, Feedback.created_at
        ).where(Feedback.status == FeedbackStatus.EXTRACTED.value)
        result = await self.session.execute(stmt)
        return [(row[0] or [], row[1], row[2]) for row in result.all()]

    async def avg_latency_ms(self) -> float | None:
        """Average LLM latency across extracted feedback. None if no rows."""
        # JSONB key access via [...].astext, then cast to numeric for AVG.
        # Postgres-specific syntax (asyncpg / SQLAlchemy 2.0).
        stmt = (
            select(
                func.avg(
                    func.cast(
                        Feedback.llm_metadata["latency_ms"].astext, Float
                    )
                )
            )
            .where(Feedback.status == FeedbackStatus.EXTRACTED.value)
            .where(Feedback.llm_metadata.isnot(None))
        )
        result = await self.session.execute(stmt)
        value = result.scalar_one_or_none()
        return float(value) if value is not None else None

    async def total_tokens(self) -> tuple[int, int]:
        """Sum of (input_tokens, output_tokens) across all extractions."""
        stmt = (
            select(
                func.sum(
                    func.cast(
                        Feedback.llm_metadata["input_tokens"].astext, Integer
                    )
                ),
                func.sum(
                    func.cast(
                        Feedback.llm_metadata["output_tokens"].astext, Integer
                    )
                ),
            )
            .where(Feedback.status == FeedbackStatus.EXTRACTED.value)
            .where(Feedback.llm_metadata.isnot(None))
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return (row[0] or 0, row[1] or 0)
