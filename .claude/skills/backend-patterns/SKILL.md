---
name: backend-patterns
description: Backend implementation patterns and code references — Pydantic Settings, JSON structured logging, custom exception hierarchy with status mapping, FastAPI DI via Annotated aliases, async SQLAlchemy session lifecycle, Postgres connection pooling, bounded asyncio.gather concurrency, FastAPI/Celery graceful shutdown, pytest fixtures. Invoke when implementing config, logging, error handling, DI, DB sessions, concurrency, shutdown, or test scaffolding for backend/app/.
---

# Backend implementation patterns

Code-heavy reference material for the FastAPI backend. Each section shows the pattern as it appears in `backend/app/`. Rules and "where things live" guidance are in `backend/CLAUDE.md`; this file is the implementation companion.

## Configuration management

All environment variables and tunable values flow through `app/config.py`.

### Pattern

```python
# app/config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # External services
    anthropic_api_key: str
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # LLM tuning
    llm_model: str = "claude-haiku-4-5"
    llm_max_tokens: int = Field(default=200, ge=1, le=4096)
    llm_timeout_seconds: int = Field(default=30, ge=1)
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_concurrency_limit: int = Field(default=5, ge=1)

    # Validation thresholds
    feedback_min_length: int = 10
    feedback_max_length: int = 5000
    feedback_min_alpha_ratio: float = 0.4

    # SSE
    sse_poll_interval_seconds: float = 1.0
    sse_max_stream_duration_minutes: int = 5

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

## Structured logging

Configured in `app/logging_config.py` at app startup. Every log line is JSON, every log line has context.

### Setup

```python
# app/logging_config.py
import logging
import sys
from pythonjsonlogger import jsonlogger


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            timestamp=True,
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
```

Called once in `app/main.py`'s lifespan setup.

### Usage rules

```python
# Good - structured fields via extra
logger.info("feedback_created", extra={
    "feedback_id": str(feedback.id),
    "request_id": request_id,
    "input_length": len(text),
})

# Bad - f-string interpolation breaks structured logging
logger.info(f"Created feedback {feedback.id} for request {request_id}")
```

### What to log

| Event | Level | Required fields |
|---|---|---|
| Endpoint entry | INFO | event, path, method, request_id |
| Service call | INFO | event, service_name, request_id, relevant IDs |
| LLM call start | INFO | event, prompt_version, input_length, request_id |
| LLM call complete | INFO | event, prompt_version, latency_ms, output_tokens, request_id |
| LLM call failed | WARNING or ERROR | event, error_type, attempt, request_id |
| Feedback skipped | INFO | event, skip_reason, feedback_id, request_id |
| Caught exception | ERROR | full traceback via logger.exception(), request_id |
| Unhandled exception | ERROR | full traceback, request_id (added by middleware) |

### Request ID propagation

A middleware adds `request_id` to every request. The ID flows through:
- Response headers (`X-Request-ID`)
- All log lines for that request (via context var)
- Celery task arguments (passed explicitly)
- LLM client metadata (for tracing)

This means every log line tied to a specific user action carries the same `request_id`. Critical for debugging.

## Error handling

### Custom exception hierarchy

Defined in `app/exceptions.py`. Each layer raises specific exception types so callers handle them precisely.

```python
class AppError(Exception):
    """Base for all application exceptions."""

class InputValidationError(AppError):
    """Input failed pre-LLM validation."""
    def __init__(self, reason: str, field: str | None = None):
        self.reason = reason
        self.field = field
        super().__init__(f"Input validation failed: {reason}")

class LLMError(AppError):
    """Base for all LLM-related failures."""

class LLMTimeoutError(LLMError):
    """LLM call exceeded timeout."""

class LLMValidationError(LLMError):
    """LLM returned output that failed schema validation after retries."""

class LLMRateLimitError(LLMError):
    """LLM API rate-limited the request."""

class DatabaseError(AppError):
    """Database operation failed unexpectedly."""
```

### Layered handling

Each layer catches what it can handle, re-raises what it can't:

- **LLM client** catches transient network errors and retries. Raises `LLMError` subclasses on terminal failures.
- **Service layer** catches `LLMError` and continues by marking feedback as failed. Doesn't catch `DatabaseError` (lets it propagate).
- **Global exception handler** in `middleware.py` catches everything else and shapes it into the JSON error response.

### Global error response shape

```json
{
  "error": "error_type_slug",
  "detail": { "field": "explanation" },
  "request_id": "uuid-string"
}
```

### Status code mapping

```python
EXCEPTION_TO_STATUS = {
    InputValidationError: 400,
    LLMError: 502,           # bad gateway, since LLM is upstream
    DatabaseError: 503,      # service unavailable
    # Anything else: 500
}
```

The global exception handler in `middleware.py` also translates `SQLAlchemyError` subclasses into `DatabaseError` before the status mapping applies, so raw ORM exceptions never reach this dict directly.

## Dependency injection

FastAPI's `Depends` for everything injectable.

### Standard dependencies

```python
# app/deps.py
from fastapi import Depends, Header
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from anthropic import AsyncAnthropic

from app.config import Settings, get_settings
from app.db import get_session


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
LLMClientDep = Annotated[AsyncAnthropic, Depends(get_llm_client)]
```

### Pattern

```python
@router.post("/feedback")
async def create_feedback(
    payload: FeedbackBatchIn,
    session: SessionDep,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> FeedbackBatchOut:
    ...
```

## Database session lifecycle

```python
# app/db.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(get_settings().database_url, echo=False)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

## Connection pooling

The async engine is created with explicit pool settings:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,         # default 10
    max_overflow=settings.db_max_overflow,   # default 20
    pool_pre_ping=True,                      # validates connection before use
    echo=False,
)
```

`pool_pre_ping=True` issues a lightweight `SELECT 1` before handing a pooled connection to a request. This prevents stale-connection errors when Postgres drops idle connections (a real failure mode after long-lived processes survive a DB restart or cloud network blip). The cost is one extra round-trip per checkout; the benefit is no surprise `OperationalError` on the first query of an idle worker.

`pool_size` is the steady-state pool; `max_overflow` allows temporary growth under load. Both come from Settings so they tune per environment without code changes.

## Concurrency patterns

### Bounded parallelism

When processing batches that involve external services (LLM, third-party APIs):

```python
async def process_batch(texts: list[str], request_id: str) -> list[ProcessResult]:
    semaphore = asyncio.Semaphore(get_settings().llm_concurrency_limit)

    async def process_with_limit(text: str) -> ProcessResult:
        async with semaphore:
            return await process_one(text, request_id)

    results = await asyncio.gather(
        *[process_with_limit(t) for t in texts],
        return_exceptions=True,
    )

    return _partition_results(results)
```

## Graceful shutdown

Two processes need shutdown discipline: the FastAPI app and the Celery worker.

**FastAPI** handles graceful shutdown automatically via the lifespan protocol. On `SIGTERM`, uvicorn stops accepting new connections, waits for in-flight requests to finish, then exits. No application-level work needed beyond using the lifespan context manager.

**Celery worker** uses two timeouts plus signal handling:

- `--soft-time-limit=N` — raises `SoftTimeLimitExceeded` inside the task at N seconds, giving the task a chance to clean up (commit a partial state, log a warning, mark feedback failed).
- `--time-limit=M` — hard kill at M seconds (M > N). The worker is forcibly terminated for that task slot.
- On `SIGTERM`, Celery finishes the currently-executing task before exiting (warm shutdown), provided the task completes within its time limit. New tasks in the queue stay queued until another worker picks them up.

Configure via `celery_worker.sh`:

```bash
celery -A app.tasks worker --soft-time-limit=120 --time-limit=180 --loglevel=info
```

The 120/180 split means: a task gets 2 minutes, with 1 minute of warning before the hard kill. For LLM extraction with 30s per-call timeout and up to 3 retries, this is a comfortable ceiling.

## Testing patterns

`backend/tests/` directory with pytest + pytest-asyncio.

### Fixtures (conftest.py)

- Test DB session (in-memory SQLite or per-test transactional rollback)
- Mocked LLM client returning predetermined responses
- Sample valid/invalid feedback texts as parameterized fixtures

### What gets tested

| Area | Tests |
|---|---|
| Validators | Every rejection rule, boundary conditions (empty, exactly min/max length, unicode, profanity) |
| LLM extraction | Mocked Anthropic responses, schema validation behavior, retry behavior on transient errors |
| Service layer | Happy path, per-item failure isolation in batch, status transitions |
| API endpoints | One integration test per endpoint: happy path + one error path |
