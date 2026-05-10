"""Audit log of every LLM call — extraction, summary, future call types.

One row per Anthropic API call. The single source of truth for LLM cost,
latency, and prompt-version analytics across the whole app. Phase 4's async
work (Celery tasks, scheduled summary regen) instruments the same table
without further refactoring.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    # BigInteger PK — audit logs grow faster than feedback rows; cheap insurance
    # against an Int4 wraparound at 2.1B if this app ever scales meaningfully.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # call_type is a LlmCallType StrEnum value. Indexed because StatsService
    # filters by type for per-type aggregations.
    call_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Model id from the API response (e.g. "claude-haiku-4-5-20251001"). Stored
    # verbatim so per-model cost analysis stays accurate when the active model
    # rotates.
    model: Mapped[str] = mapped_column(String(64), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # prompt_version powers per-version eval comparisons — "did v1.1 cost more
    # tokens than v1?" is one GROUP BY away.
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # FK back to feedback — populated for extraction calls, NULL for summary
    # calls (which aggregate over many feedback rows). ON DELETE SET NULL so
    # cost history survives feedback deletion (the call already happened and
    # cost real money — losing the row would lose audit trail).
    feedback_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("feedback.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # lazy="noload" — the relationship is rarely traversed (this is an audit
    # log, not a navigation entry point); avoid implicit JOINs.
    feedback: Mapped["Feedback | None"] = relationship("Feedback", lazy="noload")

    __table_args__ = (
        Index("ix_llm_usage_created_at", "created_at"),
        Index("ix_llm_usage_call_type", "call_type"),
    )
