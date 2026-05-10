from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import FeedbackStatus
from app.db import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    text: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=FeedbackStatus.PROCESSING.value,
        index=True,
    )
    sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    action_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
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
