from pydantic import BaseModel, ConfigDict, Field


class ThemeCount(BaseModel):
    """A theme with its occurrence count."""

    theme: str
    count: int


class SentimentBreakdown(BaseModel):
    """Count of feedback per sentiment among extracted rows."""

    positive: int = 0
    neutral: int = 0
    negative: int = 0


class SentimentTrendPoint(BaseModel):
    """Sentiment counts for a single time bucket."""

    bucket: str = Field(description="ISO date string for the time bucket (YYYY-MM-DD)")
    positive: int = 0
    neutral: int = 0
    negative: int = 0


class StatsOut(BaseModel):
    """Aggregated stats across all feedback for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_feedback: int = Field(description="Total feedback rows in any status")
    total_extracted: int = Field(description="Successfully extracted feedback")
    total_skipped: int = Field(description="Skipped during validation")
    total_failed: int = Field(description="Failed during LLM extraction")
    sentiment_breakdown: SentimentBreakdown = Field(
        description="Sentiment distribution among extracted feedback",
    )
    top_themes: list[ThemeCount] = Field(
        description="Top themes by frequency (cap from Settings.stats_top_themes_limit)",
    )
    sentiment_trend: list[SentimentTrendPoint] = Field(
        description="Daily sentiment counts (window from Settings.stats_trend_days)",
    )
    avg_latency_ms: float | None = Field(
        default=None,
        description="Average LLM latency for extracted feedback. Null if no extractions yet.",
    )
    total_input_tokens: int = Field(
        default=0,
        description="Sum of input tokens across all extractions",
    )
    total_output_tokens: int = Field(
        default=0,
        description="Sum of output tokens across all extractions",
    )
