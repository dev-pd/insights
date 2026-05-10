from collections import Counter
from datetime import datetime, timedelta, timezone

from app.constants import FeedbackStatus
from app.core.config import get_settings
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.stats import (
    SentimentBreakdown,
    SentimentTrendPoint,
    StatsOut,
    ThemeCount,
)


class StatsService:
    """Aggregates feedback rows into a single StatsOut response.

    For PoC scale (a few thousand rows), themes and sentiment trend are
    aggregated in-memory after one fetch of all extracted feedback.
    Production scale would replace with a materialized view or denormalized
    themes table; see NOTES.md for the graduation path.
    """

    def __init__(self, repo: FeedbackRepository):
        self.repo = repo

    async def compute_stats(self) -> StatsOut:
        settings = get_settings()
        top_n = settings.stats_top_themes_limit
        trend_days = settings.stats_trend_days

        # Status counts.
        status_counts = await self.repo.count_by_status()
        total_feedback = sum(status_counts.values())
        total_extracted = status_counts.get(FeedbackStatus.EXTRACTED.value, 0)
        total_skipped = status_counts.get(FeedbackStatus.SKIPPED.value, 0)
        total_failed = status_counts.get(FeedbackStatus.FAILED.value, 0)

        # Sentiment breakdown.
        sentiment_counts = await self.repo.sentiment_counts()
        sentiment_breakdown = SentimentBreakdown(
            positive=sentiment_counts.get("positive", 0),
            neutral=sentiment_counts.get("neutral", 0),
            negative=sentiment_counts.get("negative", 0),
        )

        # Themes + sentiment trend share one DB read.
        rows = await self.repo.all_themes_with_sentiment()

        # Top-N themes via Counter.
        theme_counter: Counter[str] = Counter()
        for themes, _sentiment, _created_at in rows:
            for theme in themes:
                key = theme.lower().strip()
                if key:
                    theme_counter[key] += 1
        top_themes = [
            ThemeCount(theme=theme, count=count)
            for theme, count in theme_counter.most_common(top_n)
        ]

        # Daily sentiment trend over the configured window, ending today (UTC).
        # Initialize every day in the window so the chart shows zeros, not gaps.
        now = datetime.now(timezone.utc)
        today = now.date()
        start_date = today - timedelta(days=trend_days - 1)
        trend_buckets: dict[str, dict[str, int]] = {}
        for i in range(trend_days):
            day = (start_date + timedelta(days=i)).isoformat()
            trend_buckets[day] = {"positive": 0, "neutral": 0, "negative": 0}

        cutoff_dt = datetime.combine(
            start_date, datetime.min.time(), tzinfo=timezone.utc
        )
        for _themes, sentiment, created_at in rows:
            if created_at is None or sentiment is None:
                continue
            if created_at < cutoff_dt:
                continue
            day = created_at.date().isoformat()
            if day in trend_buckets and sentiment in trend_buckets[day]:
                trend_buckets[day][sentiment] += 1

        sentiment_trend = [
            SentimentTrendPoint(bucket=day, **counts)
            for day, counts in sorted(trend_buckets.items())
        ]

        # Latency + tokens.
        avg_latency_ms = await self.repo.avg_latency_ms()
        input_tokens, output_tokens = await self.repo.total_tokens()

        return StatsOut(
            total_feedback=total_feedback,
            total_extracted=total_extracted,
            total_skipped=total_skipped,
            total_failed=total_failed,
            sentiment_breakdown=sentiment_breakdown,
            top_themes=top_themes,
            sentiment_trend=sentiment_trend,
            avg_latency_ms=avg_latency_ms,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
        )
