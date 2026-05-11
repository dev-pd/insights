"""Per-call audit log of every Anthropic invocation (extraction + summary).
Single source of truth for cost/latency/per-prompt-version analytics."""

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

    # BigInt: audit grows faster than feedback (Int4-wraparound insurance).
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # SET NULL: cost history survives feedback deletion — call cost real money.
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

    feedback: Mapped["Feedback | None"] = relationship("Feedback", lazy="noload")

    __table_args__ = (
        Index("ix_llm_usage_created_at", "created_at"),
        Index("ix_llm_usage_call_type", "call_type"),
    )
