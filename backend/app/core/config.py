from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    anthropic_api_key: SecretStr

    database_url: str
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)

    redis_url: str
    # 50 sized for SSE: each tab holds ≥1 long-lived pubsub conn plus
    # short-lived stats/summary reads. Default 10 exhausted under
    # 2 tabs + 100-item stress test → MaxConnectionsError 500s.
    redis_max_connections: int = Field(default=50, ge=5, le=500)
    # Without this the pool can block forever on degraded Redis.
    redis_socket_connect_timeout_seconds: float = Field(default=5.0, gt=0.0)

    llm_model: str = "claude-haiku-4-5"
    llm_max_tokens: int = Field(default=1024, ge=1, le=4096)
    llm_timeout_seconds: int = Field(default=30, ge=1)
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_retry_base_delay_seconds: float = Field(default=1.0, gt=0.0)
    # Caps how long a single 429 retry can park a worker. Anthropic's
    # retry-after on token-window 429s is typically <60s; 90s leaves headroom.
    llm_retry_backoff_max_seconds: float = Field(default=90.0, gt=0.0, le=600.0)
    llm_concurrency_limit: int = Field(default=5, ge=1)

    feedback_min_length: int = Field(default=10, ge=1)
    feedback_max_length: int = Field(default=5000, ge=1)
    feedback_min_alpha_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    feedback_request_max_length: int = Field(default=10_000, ge=1)
    feedback_list_default_limit: int = Field(default=50, ge=1, le=500)

    stats_trend_days: int = Field(default=14, ge=1, le=365)
    stats_theme_window_days: int = Field(default=7, ge=1, le=365)
    stats_top_themes_limit: int = Field(default=10, ge=1, le=200)

    summary_cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    # Debounce window for the summary cache invalidator. Worker emits a
    # feedback_update event per extracted/skipped/failed row; the invalidator
    # waits this many seconds of quiet before deleting the cache key — so a
    # 100-item burst collapses into ONE LLM regen on the next /summary read.
    summary_invalidation_debounce_seconds: int = Field(default=30, ge=1, le=300)
    summary_lookback_hours: int = Field(default=24, ge=1, le=168)
    summary_max_feedback_items: int = Field(default=50, ge=1, le=500)
    summary_min_feedback_items: int = Field(default=3, ge=1, le=50)
    # 120 tokens ≈ 480 chars — safety net under the v1.3 prompt's 340-char rule.
    # Lower than v1.2 (300) because the summary widget clips with line-clamp-4.
    summary_max_tokens: int = Field(default=120, ge=50, le=2048)

    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    # 3 keeps sustained throughput (~1.5 calls/s at 2s latency) close to
    # Haiku's ~0.83 calls/s ceiling; transient bursts absorbed by retries.
    celery_worker_concurrency: int = Field(default=3, ge=1, le=32)
    celery_task_soft_time_limit_seconds: int = Field(default=120, ge=10)
    celery_task_time_limit_seconds: int = Field(default=180, ge=10)
    celery_result_expires_seconds: int = Field(default=3600, ge=60)
    celery_beat_summary_cron_minute: int = Field(default=0, ge=0, le=59)
    # 12 retries × up to 120s with jitter ≈ ~10 min median total backoff —
    # sized to ride out a 100-item burst against a 50k-token/min org cap
    # (≈3 min drain) without producing FAILED rows. 6 was too tight.
    celery_extract_max_retries: int = Field(default=12, ge=0, le=20)
    celery_extract_retry_backoff_max: int = Field(default=120, ge=1, le=600)
    # Initial backoff factor for celery autoretry. Default 1 with retry_jitter
    # gives random(0, 1) on first retry → near-instant re-fire that just
    # re-trips a token-bucket 429. 10s floor pushes first retry to random(0, 10).
    celery_extract_retry_backoff_base: int = Field(default=10, ge=1, le=120)

    stress_test_max_count: int = Field(default=200, ge=1, le=1000)

    sse_heartbeat_interval_seconds: int = Field(default=30, ge=1, le=300)
    sse_poll_interval_seconds: float = Field(default=1.0, gt=0.0)
    sse_max_stream_duration_minutes: int = Field(default=5, ge=1)

    frontend_origin: str = "http://localhost:3000"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
