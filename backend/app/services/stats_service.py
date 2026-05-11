from collections import Counter
from datetime import datetime, timedelta, timezone

from app.constants import FeedbackStatus
from app.core.config import get_settings
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.schemas.stats import (
    SentimentBreakdown,
    SentimentTrendPoint,
    StatsOut,
    ThemeCount,
    TodayDelta,
)


def _percentage(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)


def _delta_pct(current: int, previous: int) -> float | None:
    if previous == 0:
        return None  # UI renders '-' instead of infinity
    return round(((current - previous) / previous) * 100, 1)


class StatsService:
    def __init__(
        self,
        repo: FeedbackRepository,
        llm_usage_repo: LlmUsageRepository,
    ):
        self.repo = repo
        self.llm_usage_repo = llm_usage_repo

    async def compute_stats(self) -> StatsOut:
        settings = get_settings()
        trend_days = settings.stats_trend_days
        theme_window_days = settings.stats_theme_window_days
        top_themes_limit = settings.stats_top_themes_limit

        status_counts = await self.repo.count_by_status()
        total_feedback = sum(status_counts.values())
        total_extracted = status_counts.get(FeedbackStatus.EXTRACTED.value, 0)
        total_skipped = status_counts.get(FeedbackStatus.SKIPPED.value, 0)
        total_failed = status_counts.get(FeedbackStatus.FAILED.value, 0)
        pending_count = status_counts.get(FeedbackStatus.PROCESSING.value, 0)

        sentiment_counts = await self.repo.sentiment_counts()
        positive = sentiment_counts.get("positive", 0)
        neutral = sentiment_counts.get("neutral", 0)
        negative = sentiment_counts.get("negative", 0)
        sentiment_breakdown = SentimentBreakdown(
            positive=positive,
            neutral=neutral,
            negative=negative,
        )
        positive_pct = _percentage(positive, total_extracted)
        negative_pct = _percentage(negative, total_extracted)

        # 24h windows anchored on `now` (not midnight) match the AI summary widget's lookback.
        now = datetime.now(timezone.utc)
        today_start = now - timedelta(hours=24)
        yesterday_start = now - timedelta(hours=48)
        today_count = await self.repo.count_in_window(today_start, now)
        yesterday_count = await self.repo.count_in_window(yesterday_start, today_start)
        today_delta = TodayDelta(
            today_count=today_count,
            yesterday_count=yesterday_count,
            delta_pct=_delta_pct(today_count, yesterday_count),
        )

        rows = await self.repo.all_themes_with_sentiment()

        theme_window_start = now - timedelta(days=theme_window_days)
        theme_counter: Counter[str] = Counter()
        for themes, _sentiment, created_at in rows:
            if created_at is None or created_at < theme_window_start:
                continue
            for theme in themes:
                key = theme.lower().strip()
                if key:
                    theme_counter[key] += 1
        top_themes = [
            ThemeCount(theme=theme, count=count)
            for theme, count in theme_counter.most_common(top_themes_limit)
        ]

        # Pre-init every day so the chart shows zeros, not gaps.
        today = now.date()
        start_date = today - timedelta(days=trend_days - 1)
        trend_buckets: dict[str, dict[str, int]] = {}
        for day_offset in range(trend_days):
            day = (start_date + timedelta(days=day_offset)).isoformat()
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

        # llm_usage covers all call types (extraction + summary), not just per-feedback.
        avg_latency_ms = await self.llm_usage_repo.avg_latency_ms()
        input_tokens, output_tokens = await self.llm_usage_repo.total_tokens()

        return StatsOut(
            total_feedback=total_feedback,
            total_extracted=total_extracted,
            total_skipped=total_skipped,
            total_failed=total_failed,
            pending_count=pending_count,
            sentiment_breakdown=sentiment_breakdown,
            positive_pct=positive_pct,
            negative_pct=negative_pct,
            today_delta=today_delta,
            top_themes=top_themes,
            sentiment_trend=sentiment_trend,
            avg_latency_ms=avg_latency_ms,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
        )
