# Production patterns

Cross-cutting patterns that apply across the codebase. These are the practices that elevate a PoC into something that resembles production code at small scale. Each pattern is scaled appropriately to project size, not omitted.

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

### Rules

- One Settings class. No scattered `os.environ.get()` calls in business code.
- Cached singleton via `@lru_cache`. Avoids re-parsing `.env` on every call.
- Inject via `Depends(get_settings)` in FastAPI endpoints. Never import the global directly inside business logic.
- Validation via Pydantic field constraints (`ge=`, `le=`) catches misconfiguration at startup.
- Sensitive values (API keys, DB URLs) load from env vars. Never commit them.

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

### Rules

- Never bare `except:`. Always specify the exception type.
- Never `except Exception` without a clear comment explaining why.
- Always log before re-raising or handling. Never swallow silently.
- User-facing messages are short and actionable. Internal details go in logs only.

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

### Rules

- Services accept dependencies as parameters, never import them at module level.
- This makes testing trivial: pass mocks instead of patching imports.
- One source of truth for each dependency provider, in `deps.py`.
- The `Annotated[Type, Depends(provider)]` pattern is reusable; alias common ones.

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

### Rules

- One session per request, scoped via FastAPI dependency.
- Auto-commit on successful return, auto-rollback on exception.
- Sessions never escape the request context. No global sessions.
- Background tasks (Celery) get their own session via the same factory, scoped to the task.

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

### Rules

- `return_exceptions=True` so one item's failure doesn't abort the batch.
- Bounded by `Semaphore` so we don't overwhelm downstream services.
- Each task isolated: own DB session, own try/except, own logging context.
- The Semaphore size lives in Settings (`llm_concurrency_limit`), not as a magic number.

## LLM client patterns

The Anthropic client is wrapped in `app/llm/client.py` to add production behavior.

### Wrapper responsibilities

- **Retries**: on 429, 500-503 with exponential backoff (1s, 2s, 4s; max attempts from Settings)
- **Timeout**: per-call, from Settings
- **Logging**: every call logs prompt_version, input_length, latency_ms, output_tokens, success/failure
- **Error mapping**: HTTPX exceptions → custom LLM exception types
- **Bounded concurrency**: module-level Semaphore for parallel calls

### Pattern

```python
import asyncio
import time
from anthropic import AsyncAnthropic, APIStatusError, APITimeoutError

from app.config import get_settings
from app.exceptions import LLMError, LLMTimeoutError, LLMRateLimitError


_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().llm_concurrency_limit)
    return _semaphore


async def call_llm(client: AsyncAnthropic, request_id: str, **kwargs) -> str:
    settings = get_settings()
    last_error: Exception | None = None

    async with _get_semaphore():
        for attempt in range(settings.llm_max_retries + 1):
            start = time.monotonic()
            try:
                response = await client.messages.create(
                    timeout=settings.llm_timeout_seconds,
                    **kwargs,
                )
                logger.info("llm_call_complete", extra={
                    "latency_ms": int((time.monotonic() - start) * 1000),
                    "attempt": attempt,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "request_id": request_id,
                })
                return response.content[0].text

            except APITimeoutError as e:
                last_error = LLMTimeoutError(str(e))
                logger.warning("llm_call_failed", extra={
                    "event": "llm_call_failed",
                    "error_type": type(e).__name__,
                    "attempt": attempt,
                    "request_id": request_id,
                })
            except APIStatusError as e:
                if e.status_code == 429:
                    last_error = LLMRateLimitError(str(e))
                elif e.status_code >= 500:
                    last_error = LLMError(str(e))
                else:
                    logger.warning("llm_call_failed", extra={
                        "event": "llm_call_failed",
                        "error_type": type(e).__name__,
                        "attempt": attempt,
                        "request_id": request_id,
                    })
                    raise LLMError(str(e)) from e
                logger.warning("llm_call_failed", extra={
                    "event": "llm_call_failed",
                    "error_type": type(e).__name__,
                    "attempt": attempt,
                    "request_id": request_id,
                })

            if attempt < settings.llm_max_retries:
                await asyncio.sleep(2 ** attempt)

    logger.error("llm_call_terminal_failure", extra={
        "event": "llm_call_terminal_failure",
        "error_type": type(last_error).__name__ if last_error else "Unknown",
        "request_id": request_id,
    })
    raise last_error or LLMError("All retries exhausted")
```

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

### Rules

- LLM calls always mocked. No real API calls in test runs.
- Each test is independent; no shared state across tests.
- Test names describe the behavior, not the implementation: `test_too_short_input_is_skipped` not `test_validate_returns_false`.
- Coverage target: meaningful tests on critical paths, not 100% line coverage.

## Frontend production patterns

These apply to React components in `frontend/`.

### Error boundaries

Wrap major sections (the page-level layout, the dashboard, each chart) in error boundaries via Next.js's `error.tsx` files. One component crashing should never blank the whole page.

### Loading states

Every async render path has a skeleton loader, not a spinner. Skeletons:
- Communicate the shape of incoming content
- Don't shift layout when real content loads
- Use shadcn/ui's `Skeleton` component for consistency

### Optimistic updates (when appropriate)

For the feedback submission flow:
- Show the new row immediately with status `processing`
- The backend confirms via SSE
- If submission fails, show an error and remove the row

This makes the UI feel instant. The pattern lives in the submission hook, not scattered across components.

### Accessibility floor

- Every interactive element keyboard-accessible
- Form inputs have visible labels
- Color is never the only signal (sentiment cards include the label text)
- Focus indicators visible (don't override Tailwind's default focus rings)

## Migration to full production

These patterns are intentionally scaled for the PoC. A graduation path to full production:

| Concern | PoC approach | Production approach |
|---|---|---|
| DB migrations | Fresh schema on `docker compose up` | Alembic migrations |
| Error tracking | Logs only | Sentry / Datadog APM |
| Tracing | request_id in logs | OpenTelemetry across services |
| Metrics | None | Prometheus: LLM call counts, latencies, error rates |
| Secrets | `.env` file | AWS Secrets Manager / Vault |
| Auth | None (PoC) | API keys, JWT, request signing |
| Rate limiting | None | Per-client limits (e.g. slowapi) |
| Queue | Redis broker | Dedicated infrastructure with DLQ |
| Deploys | docker-compose | Kubernetes with rolling deploys |

Each is a clean addition without restructuring existing code, because the patterns above already enforce the right boundaries.

## The signal these patterns send

A senior reviewer reading this codebase should immediately see:

- Configuration is centralized, not scattered
- Errors have a hierarchy and intentional handling
- Logs are structured and traceable
- Layers don't bleed into each other
- Concurrency is bounded and resilient
- Testing focuses on critical behavior, not coverage theater
- The frontend handles real-world conditions (loading, errors, empty)

These aren't "nice to haves." They're the difference between code you ship and code you write.