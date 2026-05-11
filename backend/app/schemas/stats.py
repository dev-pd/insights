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


class TodayDelta(BaseModel):
    """24h-vs-prior-24h volume comparison. 24h window (not 7-day) keeps the
    number distinct from `total_feedback` on short-lived demos and matches
    the AI summary widget's cohort."""

    today_count: int = Field(description="Total feedback in the last 24 hours.")
    yesterday_count: int = Field(
        description="Total feedback in the prior 24-hour window (24-48 hours ago)."
    )
    delta_pct: float | None = Field(
        default=None,
        description="Percent change vs yesterday. Null when yesterday's count was zero "
        "(division-by-zero — UI shows '-' rather than infinity).",
    )


class StatsOut(BaseModel):
    """Aggregated stats across all feedback for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_feedback: int = Field(description="Total feedback rows in any status")
    total_extracted: int = Field(description="Successfully extracted feedback")
    total_skipped: int = Field(description="Skipped during validation")
    total_failed: int = Field(description="Failed during LLM extraction")
    pending_count: int = Field(
        default=0,
        description="Feedback currently being processed by a Celery worker.",
    )
    sentiment_breakdown: SentimentBreakdown = Field(
        description="Sentiment distribution among extracted feedback",
    )
    positive_pct: float = Field(
        default=0.0,
        description="Percent of extracted feedback labeled positive. 0.0 when none extracted.",
    )
    negative_pct: float = Field(
        default=0.0,
        description="Percent of extracted feedback labeled negative. 0.0 when none extracted.",
    )
    today_delta: TodayDelta = Field(
        description="Day-over-day change in submission volume.",
    )
    top_themes: list[ThemeCount] = Field(
        description="Top themes within the last `stats_theme_window_days` days, "
        "capped at `stats_top_themes_limit`.",
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
