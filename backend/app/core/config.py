from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file.

    All env vars and defaults match `backend/.env.example`. Mutating settings
    in-process is unsupported; the singleton is cached for the lifetime of the
    process via `@lru_cache` on `get_settings()`.
    """

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

    llm_model: str = "claude-haiku-4-5"
    llm_max_tokens: int = Field(default=1024, ge=1, le=4096)
    llm_timeout_seconds: int = Field(default=30, ge=1)
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_retry_base_delay_seconds: float = Field(default=1.0, gt=0.0)
    llm_concurrency_limit: int = Field(default=5, ge=1)

    feedback_min_length: int = Field(default=10, ge=1)
    feedback_max_length: int = Field(default=5000, ge=1)
    feedback_min_alpha_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    feedback_request_max_length: int = Field(default=10_000, ge=1)
    feedback_list_default_limit: int = Field(default=50, ge=1, le=500)

    sse_poll_interval_seconds: float = Field(default=1.0, gt=0.0)
    sse_max_stream_duration_minutes: int = Field(default=5, ge=1)

    frontend_origin: str = "http://localhost:3000"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
