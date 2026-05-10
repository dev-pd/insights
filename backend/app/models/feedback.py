from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import FeedbackStatus
from app.db import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=FeedbackStatus.PROCESSING.value,
        index=True,
    )
    sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    themes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    action_items: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_feedback_status_created_at", "status", "created_at"),
    )
