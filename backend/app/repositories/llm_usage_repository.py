"""Data access for the llm_usage audit table.

Single write path for all LLM call sites — extraction service, summary
service, and (Phase 4) Celery tasks. Aggregation methods power the
dashboard cost KPIs.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LlmUsage


class LlmUsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        call_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int | None = None,
        prompt_version: str | None = None,
        feedback_id: int | None = None,
    ) -> LlmUsage:
        """Insert one usage row. Caller's session is responsible for committing
        — the FastAPI request-scoped session in `db.get_session` commits on
        successful return, so callers in the request path don't need to do
        anything beyond awaiting this method."""
        usage = LlmUsage(
            call_type=call_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            prompt_version=prompt_version,
            feedback_id=feedback_id,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def total_tokens(self, call_type: str | None = None) -> tuple[int, int]:
        """Return (input_tokens, output_tokens) summed across usage.

        Filters to a single call type when provided. Returns (0, 0) when
        there's no data — `func.coalesce` keeps None out of the response
        on an empty table.
        """
        stmt = select(
            func.coalesce(func.sum(LlmUsage.input_tokens), 0),
            func.coalesce(func.sum(LlmUsage.output_tokens), 0),
        )
        if call_type is not None:
            stmt = stmt.where(LlmUsage.call_type == call_type)
        result = await self.session.execute(stmt)
        row = result.one()
        return (int(row[0]), int(row[1]))

    async def avg_latency_ms(self, call_type: str | None = None) -> float | None:
        """Average latency across LLM calls. None when there's no data with
        a recorded latency value."""
        stmt = select(func.avg(LlmUsage.latency_ms)).where(
            LlmUsage.latency_ms.isnot(None)
        )
        if call_type is not None:
            stmt = stmt.where(LlmUsage.call_type == call_type)
        result = await self.session.execute(stmt)
        value = result.scalar_one_or_none()
        return float(value) if value is not None else None

    async def count(self, call_type: str | None = None) -> int:
        """Total LLM call count, optionally filtered by type."""
        stmt = select(func.count(LlmUsage.id))
        if call_type is not None:
            stmt = stmt.where(LlmUsage.call_type == call_type)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
