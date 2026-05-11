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
        # Flush only — caller commits (request DI / worker_session_scope).
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
        # coalesce → 0, not None, on an empty table.
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
        stmt = select(func.avg(LlmUsage.latency_ms)).where(
            LlmUsage.latency_ms.isnot(None)
        )
        if call_type is not None:
            stmt = stmt.where(LlmUsage.call_type == call_type)
        result = await self.session.execute(stmt)
        value = result.scalar_one_or_none()
        return float(value) if value is not None else None

    async def count(self, call_type: str | None = None) -> int:
        stmt = select(func.count(LlmUsage.id))
        if call_type is not None:
            stmt = stmt.where(LlmUsage.call_type == call_type)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
