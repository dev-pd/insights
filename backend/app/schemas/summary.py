from typing import Any

from pydantic import BaseModel, Field


class SummaryOut(BaseModel):
    text: str = Field(description="The AI-generated summary text.")
    generated_at: str = Field(
        description="ISO 8601 UTC timestamp of when this summary was generated."
    )
    feedback_count: int = Field(
        description="Number of feedback items that fed into the summary."
    )
    cached: bool = Field(
        description="True if returned from Redis cache, False if freshly generated."
    )
    error: str | None = Field(
        default=None,
        description="Set to the underlying error message when generation failed. "
        "Failures are NOT cached so the next request retries.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="LLM call metadata (tokens, latency, prompt_version, model). "
        "Null on the 'not enough data' path and on errors.",
    )
