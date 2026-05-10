from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str
    status: str
    sentiment: str | None = None
    themes: list[str] | None = None
    action_items: list[str] | None = None
    language: str | None = None
    skip_reason: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: bool
    redis: bool


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str
