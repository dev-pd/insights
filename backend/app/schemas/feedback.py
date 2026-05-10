from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    status: str
    sentiment: str | None = None
    themes: list[str] = []
    action_items: list[str] = []
    language: str | None = None
    skip_reason: str | None = None
    llm_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class FeedbackListResponse(BaseModel):
    items: list[FeedbackOut]


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str
