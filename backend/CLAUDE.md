# Backend conventions

How to write Python code in this project. Applies to everything under `backend/`. These are non-negotiable conventions: when generating or editing backend code, follow them without exception.

## Folder structure

```
backend/app/
├── api/
│   ├── deps.py                  # API-level dependencies
│   ├── health.py                # Operational endpoints (/health, /ready)
│   └── v1/
│       ├── router.py            # v1_router composition
│       └── routes/
│           ├── feedback.py      # POST /v1/feedback, GET /v1/feedback
│           └── stats.py         # GET /v1/stats (Phase 4 will add /events SSE)
├── core/
│   ├── config.py                # Pydantic Settings
│   └── logging.py               # JSON logging setup
├── middleware/
│   ├── request_id.py            # RequestIDMiddleware
│   └── exceptions.py            # Exception handlers
├── models/
│   └── feedback.py              # Feedback SQLAlchemy model
├── repositories/
│   └── feedback_repository.py   # Data access for Feedback (CRUD + aggregations)
├── schemas/
│   ├── feedback.py              # FeedbackOut, FeedbackListResponse, ErrorResponse
│   ├── health.py                # HealthResponse, ReadyResponse
│   └── stats.py                 # StatsOut, ThemeCount, SentimentBreakdown, SentimentTrendPoint
├── services/
│   ├── feedback_service.py      # validate → extract → persist
│   └── stats_service.py         # aggregate counts, themes, trends
├── llm/                         # client, extract, validate, schema
│   └── prompts/                 # v1.py + __init__ selects ACTIVE
├── constants.py                 # FeedbackStatus, SkipReason StrEnums
├── db.py                        # Engine, Base, async session factory ONLY
├── exceptions.py                # AppError hierarchy
└── main.py                      # App factory, lifespan, router mounting

backend/tests/                   # pytest tests (Phase 5)
backend/evals/                   # Standalone eval scripts (Phase 5)
```

## Python version and tooling

- Python 3.13 minimum. Use modern syntax: `str | None` instead of `Optional[str]`, `list[str]` instead of `List[str]`.
- Package management via `uv`. Never `pip install` directly; always `uv add` or edit `pyproject.toml`.
- Run scripts with `uv run`. Run tests with `uv run pytest`.

### Library versions (May 2026)

All on latest stable per the locked `uv.lock`:

- **FastAPI** 0.136.x
- **Pydantic** 2.13.x
- **pydantic-settings** 2.14.x
- **SQLAlchemy** 2.0.49 (async)
- **asyncpg** 0.31.x
- **uvicorn** 0.46.x
- **Anthropic Python SDK** 0.100.x
- **Celery** 5.6.x, **redis-py** 7.4.x
- **pytest** 9.0.x, **pytest-asyncio** 1.3.x
- **httpx** 0.28.x, **ruff** 0.15.x

## Naming

| Element | Convention | Example |
|---|---|---|
| Module file | snake_case | `feedback_service.py` |
| Function | snake_case | `extract_insights`, `is_processable` |
| Async function | snake_case (no `async_` prefix) | `process_batch` not `async_process_batch` |
| Class | PascalCase | `Feedback`, `ExtractionResult` |
| Constant | UPPER_SNAKE_CASE | `LLM_TIMEOUT_SECONDS`, `MAX_RETRY_ATTEMPTS` |
| Private function/var | leading underscore | `_save_pending`, `_LLM_SEMAPHORE` |
| Type alias | PascalCase | `FeedbackId = uuid.UUID` |
| Enum class | PascalCase | `FeedbackStatus` |
| Enum member | UPPER_SNAKE_CASE | `FeedbackStatus.PROCESSING` |

### No single-letter variables

Loop variables, comprehension variables, and exception bindings get descriptive names. The codebase reads from many angles (PR review, grep, AI assistants, future you); a one-letter name forces the reader to reconstruct what it represents from surrounding code, every time.

```python
# Good
extracted = sum(1 for feedback in results if feedback.status == "extracted")
items = [FeedbackOut.model_validate(feedback) for feedback in results]
for index, text in enumerate(texts):
    ...
try:
    ...
except LLMError as error:
    log.exception("llm_failed", extra={"error_type": type(error).__name__})

# Bad
extracted = sum(1 for r in results if r.status == "extracted")
items = [FeedbackOut.model_validate(r) for r in results]
for i, text in enumerate(texts):
    ...
except LLMError as e:
    log.exception("llm_failed", extra={"error_type": type(e).__name__})
```

The bar: would a reader unfamiliar with the function understand the variable's meaning at the point of first use? If not, rename.

**Allowed exceptions:**
- Literal `_` for "I'm ignoring this." `for _themes, sentiment, created_at in rows:` is fine when only sentiment/created_at are used.
- Math/physics conventions where the single letter IS the domain language: `x, y, z` for coordinates; `dx, dy` for deltas in chart layout code.

Default to descriptive — and pick a name that says what the value *is* in the domain (`feedback`, `theme`, `error`), not just its type (`obj`, `item`, `e`).

## Type hints

Required on every function signature (parameters and return type). No exceptions.

```python
# Good
async def extract_insights(text: str, request_id: str) -> ExtractionResult:
    ...

# Bad - missing return type
async def extract_insights(text: str, request_id: str):
    ...

# Bad - missing parameter types
async def extract_insights(text, request_id):
    ...
```

Use modern union syntax (`X | None`) and built-in generics (`list[X]`, `dict[X, Y]`) instead of `typing.Optional` or `typing.List`.

For FastAPI dependency injection and Pydantic field constraints, use `Annotated`:

```python
from typing import Annotated
from fastapi import Depends, Query

async def search_feedback(
    q: Annotated[str | None, Query(max_length=200)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> FeedbackListResponse:
    ...
```

## Pydantic

All API request and response shapes are Pydantic models. Defined in `app/schemas.py`. Never accept or return raw `dict` from an API endpoint.

```python
# Good
class FeedbackBatchIn(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=100)

@router.post("/feedback")
async def create_feedback(payload: FeedbackBatchIn) -> FeedbackBatchOut:
    ...

# Bad - raw dict in/out
@router.post("/feedback")
async def create_feedback(payload: dict) -> dict:
    ...
```

LLM output is validated through Pydantic in `app/llm/schema.py`. Configuration is validated through Pydantic Settings in `app/config.py`.

Use `Field(..., description="...")` for non-obvious fields. The description shows up in generated OpenAPI docs.

## Configuration

All environment variables and tunable values flow through `app/config.py`. Implementation reference (full `Settings` class, `@lru_cache` singleton) lives in the `backend-patterns` skill. Rules:

- One Settings class. No scattered `os.environ.get()` calls in business code.
- Cached singleton via `@lru_cache`. Avoids re-parsing `.env` on every call.
- Inject via `Depends(get_settings)` in FastAPI endpoints. Never import the global directly inside business logic.
- Validation via Pydantic field constraints (`ge=`, `le=`) catches misconfiguration at startup.
- Sensitive values (API keys, DB URLs) load from env vars. Never commit them.

## Structured logging

Configured in `app/logging_config.py` at app startup. Every log line is JSON, every log line has context. Setup code in the `backend-patterns` skill.

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

## API router composition

API routers in `app/api/` use sub-routers organized under a v1 router prefix. The router composition lives in `app/api/__init__.py`: `v1_router` gets `prefix="/v1"`, `ops_router` stays unprefixed. `main.py` mounts both.

## Database indexes

All queryable columns have explicit indexes in the SQLAlchemy model. `Feedback` table indexes:

- `status` — filtered constantly (list-by-status, processing-rows scan).
- `created_at` — sort key for the feedback list.
- Composite `(status, created_at)` — for the processing-rows-by-time scan that the SSE endpoint uses.

Indexes are declared on the model, not added later via Alembic. Adding them at model definition guarantees they're created on `Base.metadata.create_all()` for the PoC bootstrap.

## Database session lifecycle

Async session via FastAPI dependency. Engine setup and `get_session` factory in the `backend-patterns` skill. Rules:

- One session per request, scoped via FastAPI dependency.
- Auto-commit on successful return, auto-rollback on exception.
- Sessions never escape the request context. No global sessions.
- Background tasks (Celery) get their own session via the same factory, scoped to the task.

## Connection pooling

The async engine is created with explicit pool settings (full code in `backend-patterns` skill):

- `pool_size=settings.db_pool_size` (default 10) — steady-state pool.
- `max_overflow=settings.db_max_overflow` (default 20) — temporary growth under load.
- `pool_pre_ping=True` — issues a lightweight `SELECT 1` before handing a pooled connection to a request. Prevents stale-connection errors when Postgres drops idle connections (a real failure mode after long-lived processes survive a DB restart or cloud network blip).

Both `pool_size` and `max_overflow` come from Settings so they tune per environment without code changes.

## Request body size limits

Configure starlette's `Limits` middleware (or equivalent) to cap raw request body at 1MB. Pydantic field-level length caps (e.g. `max_length=5000` on feedback text) are separate; this is the outer wall against malicious payloads — protects the parser before Pydantic ever sees the body.

## CORS configuration

The docker-compose stack uses nginx in front of both backend and frontend, so the browser sees a single origin and CORS is not needed at runtime. `CORSMiddleware` is still installed in `main.py` with `allow_origins` from `Settings.frontend_origin` (default `http://localhost:3000`) as a defense-in-depth measure: if someone bypasses nginx and hits the backend directly during debugging, the middleware enforces an explicit allowed-origin list rather than silently accepting all origins. Never use `allow_origins=["*"]` in any deployment.

## Proxy header handling

`uvicorn` always runs with `--proxy-headers --forwarded-allow-ips=*` because nginx is always in front. This makes FastAPI honor `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Forwarded-Host` from nginx, so the request_id middleware and any future per-IP rate limiting see real client IPs (not nginx's IP, which would be the immediate peer).

## No magic values

**Non-negotiable for Phase 2-5 code.** If a value could vary, repeat, or change with environment, it does NOT live inline in code.

### Where each kind of value lives

| Type of value | Where it lives | Imported via |
|---|---|---|
| Tunable thresholds (timeouts, retry counts, page sizes, validation limits, model id, max_tokens) | `app/core/config.py` `Settings` (loaded from `.env`) | `from app.core.config import get_settings; settings = get_settings()` |
| Status strings, skip reasons, enum-like strings | `app/constants.py` as `StrEnum` classes | `from app.constants import FeedbackStatus, SkipReason` |
| HTTP status codes | `fastapi.status.HTTP_*` constants | `from fastapi import status` |
| Secrets (API keys, DB URLs) | `Settings` fields typed as `SecretStr` | same as Settings |
| Repeated string literals (tool names, log event names) | Module-level `UPPER_SNAKE_CASE` constants in the file that owns the concept | direct import |
| API contract constraints (Pydantic `Field(min_length=, max_length=)` on response shapes — `ExtractionResult.themes` etc.) | **Stay inline** in `app/llm/schema.py` / `app/schemas/*.py` | n/a — these define the contract; changing them is a breaking change, not a config change |

```python
# Good
from app.core.config import get_settings
from app.constants import FeedbackStatus
from fastapi import status

settings = get_settings()
if elapsed > settings.llm_timeout_seconds:
    raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, ...)
feedback.status = FeedbackStatus.PROCESSING

# Bad
if elapsed > 30:
    raise HTTPException(status_code=504, ...)
feedback.status = "processing"
```

### Currently defined Settings fields (May 2026)

For reference when wiring new code — pick the existing field rather than redefining one:

- **External services:** `anthropic_api_key`, `database_url`, `db_pool_size`, `db_max_overflow`, `redis_url`
- **LLM tuning:** `llm_model`, `llm_max_tokens`, `llm_timeout_seconds`, `llm_max_retries`, `llm_retry_base_delay_seconds`, `llm_concurrency_limit`
- **Validation thresholds:** `feedback_min_length`, `feedback_max_length`, `feedback_min_alpha_ratio`
- **API limits:** `feedback_request_max_length` (POST body cap), `feedback_list_default_limit` (GET page size)
- **Stats:** `stats_trend_days` (sentiment-trend window). Themes endpoint returns all themes; no cap.
- **SSE (Phase 4):** `sse_poll_interval_seconds`, `sse_max_stream_duration_minutes`
- **Other:** `frontend_origin`, `log_level`

### Workflow when you need a new tunable

1. **Add a field to `Settings`** in `app/core/config.py` with a sensible default and Pydantic constraint (`Field(default=X, ge=Y, le=Z)`).
2. **Add the env var to `backend/.env.example`** with the same default and a one-line comment if non-obvious. Group under the right section (LLM / validation / API limits / etc.).
3. **Read it in code** via `get_settings().<field>` — never via `os.environ` directly.
4. **Don't add a backstop module constant.** No `MIN_LENGTH = 10` next to the Settings field; pick one source of truth.

### Rule of thumb

- Number or non-enum string appears in **two or more files** → it's a constant.
- Number or string is **tunable per environment** (dev vs docker vs prod) → it's a Settings field.
- Number or string defines the **API contract that clients depend on** (response shape, schema constraints) → it stays inline in the schema where the contract lives.

Phase 2-5 code MUST NOT introduce new module-level numeric/string constants for tunables. New tunables become Settings fields.

## Async patterns

Every endpoint is `async`. Every database call goes through the async SQLAlchemy session. Every LLM call goes through the async wrapped client.

### asyncio.gather for parallel work

```python
import asyncio

# Good - parallel with bounded concurrency
async def process_batch(texts: list[str]) -> list[FeedbackOut]:
    semaphore = asyncio.Semaphore(5)
    
    async def process_with_limit(text: str) -> FeedbackOut:
        async with semaphore:
            return await process_one(text)
    
    results = await asyncio.gather(
        *[process_with_limit(text) for text in texts],
        return_exceptions=True,
    )
    return [r for r in results if not isinstance(r, Exception)]

# Bad - sequential, no concurrency
async def process_batch(texts: list[str]) -> list[FeedbackOut]:
    results = []
    for text in texts:
        results.append(await process_one(text))
    return results
```

### return_exceptions=True for fault isolation

When using `asyncio.gather` for batch work, always set `return_exceptions=True` so one failure does not abort the entire batch. Then handle exceptions per-item.

### Bounded concurrency

When calling external services (LLM API, third-party HTTP), use `asyncio.Semaphore` to bound parallel calls. The limit lives in `config.py` as a Setting.

### Additional concurrency rules

- Each task isolated: own DB session, own try/except, own logging context.
- The Semaphore size lives in Settings (`llm_concurrency_limit`), not as a magic number.

## Dependency injection

FastAPI's `Depends` for everything injectable. Standard `Annotated` aliases (`SettingsDep`, `SessionDep`, `RequestIdDep`, `LLMClientDep`) live in `app/deps.py`. Pattern code in `backend-patterns` skill. Rules:

- Services accept dependencies as parameters, never import them at module level.
- This makes testing trivial: pass mocks instead of patching imports.
- One source of truth for each dependency provider, in `deps.py`.
- The `Annotated[Type, Depends(provider)]` pattern is reusable; alias common ones.

## Repository pattern

All data access lives in `app/repositories/`. One repository per aggregate root (Feedback is the only one for this PoC).

### Structure

Each repository:
- Takes an `AsyncSession` in the constructor
- Exposes async methods returning domain types (the SQLAlchemy model is the domain type for this PoC; for larger projects you'd map to separate domain dataclasses)
- Never returns raw query results, dicts, or rows
- Hides all SQLAlchemy specifics: `select()`, `where()`, `scalars()`, `execute()` calls live ONLY here

### Where models live

SQLAlchemy entity definitions live in `app/models/`, one file per entity. Models import `Base` from `app.db`. Repositories import entities from `app.models`. Services never import models or `db.py` directly — they go through repositories.

This separation matters even at PoC scale: `db.py` becomes a stable infrastructure module that rarely changes, `models/` evolves with the domain, and the boundary makes "where do I add a new entity" trivially answerable.

### Pattern

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FeedbackStatus
from app.models.feedback import Feedback


class FeedbackRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, feedback_id: UUID) -> Feedback | None:
        result = await self.session.execute(
            select(Feedback).where(Feedback.id == feedback_id)
        )
        return result.scalar_one_or_none()

    async def create(self, text: str, status: FeedbackStatus) -> Feedback:
        feedback = Feedback(text=text, status=status)
        self.session.add(feedback)
        await self.session.flush()
        return feedback
```

### Rules

- One repository class per aggregate root.
- Repository methods are async.
- Repository methods never raise `HTTPException`. They raise domain exceptions (`DatabaseError`, `NotFoundError`) and let the service layer translate.
- Repository methods never construct response shapes. That's the service's job.
- Use `session.flush()` to assign IDs without committing; commits happen at the request boundary via the `get_session` dependency.
- Aggregations and complex queries also live in the repository, not the service.

### Service usage

Services receive repositories via FastAPI dependency injection:

```python
@router.post("/feedback")
async def create_feedback(
    payload: FeedbackBatchIn,
    repo: Annotated[FeedbackRepository, Depends(get_feedback_repository)],
    ...
) -> FeedbackBatchOut:
    return await feedback_service.create_batch(repo, payload, ...)
```

Where `get_feedback_repository` wraps the session dependency:

```python
async def get_feedback_repository(
    session: SessionDep,
) -> FeedbackRepository:
    return FeedbackRepository(session)
```

## Imports

Order: standard library → third-party → local app modules. Within each group, alphabetical. Use absolute imports always.

```python
# Good
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Feedback, get_session
from app.llm.extract import extract_insights
from app.schemas import FeedbackBatchIn, FeedbackBatchOut

# Bad - wildcard import
from fastapi import *

# Bad - relative import
from ..llm.extract import extract_insights
```

No wildcard imports. No relative imports.

## Error messages

Two audiences for error messages: the user (via API response) and the operator (via logs). They have different needs.

### User-facing (API response detail)

- Short, actionable, no jargon.
- Never expose internal details (stack traces, SQL, internal paths).
- Use the structured error response shape: `{ error, detail, request_id }`.

```python
# Good
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={"error": "input_too_long", "field": "text", "max_length": 5000},
)

# Bad - exposes internals
raise HTTPException(
    status_code=400,
    detail=f"InputValidator.check_length failed at line 42: {repr(text)[:200]}",
)
```

### Logs (for operators)

- Structured with context: include `request_id`, `feedback_id`, relevant input characteristics.
- Use `logger.exception()` to capture full traceback on caught exceptions.
- Use `logger.warning()` for handled-but-noteworthy issues.
- See the `Structured logging` section above for the full contract.

## Custom exceptions

Defined in `app/exceptions.py`. Each layer raises specific exception types so callers can handle them precisely.

```python
class AppError(Exception):
    """Base for all application exceptions."""

class InputValidationError(AppError):
    """Input failed pre-LLM validation."""

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

Catch what you can handle. Re-raise what you can't. Never bare `except:`. Never `except Exception` without a clear reason.

```python
# Good
try:
    extraction = await extract_insights(text)
except LLMTimeoutError:
    logger.warning("llm_timeout", extra={"feedback_id": feedback_id})
    return await mark_failed(feedback_id, reason="llm_timeout")
except LLMError as e:
    logger.exception("llm_terminal_error", extra={"feedback_id": feedback_id})
    return await mark_failed(feedback_id, reason="llm_error")

# Bad - swallows all exceptions silently
try:
    extraction = await extract_insights(text)
except:
    pass
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

### Additional rules

- Never bare `except:`. Always specify the exception type.
- Never `except Exception` without a clear comment explaining why.
- Always log before re-raising or handling. Never swallow silently.
- User-facing messages are short and actionable. Internal details go in logs only.

## Graceful shutdown

Two processes need shutdown discipline: the FastAPI app and the Celery worker. Implementation flags and `celery_worker.sh` example in `backend-patterns` skill.

- **FastAPI** handles graceful shutdown automatically via the lifespan protocol. On `SIGTERM`, uvicorn stops accepting new connections, waits for in-flight requests to finish, then exits. No application-level work needed beyond using the lifespan context manager.
- **Celery worker** uses `--soft-time-limit=120` (raises `SoftTimeLimitExceeded` for cleanup) and `--time-limit=180` (hard kill). On `SIGTERM`, Celery finishes the currently-executing task before exiting (warm shutdown), provided the task completes within its time limit. New tasks in the queue stay queued until another worker picks them up.

The 120/180 split means: a task gets 2 minutes, with 1 minute of warning before the hard kill. For LLM extraction with 30s per-call timeout and up to 3 retries, this is a comfortable ceiling.

## Functions and modules

### Function size

Keep functions focused. If a function is over 40 lines, consider whether it should be split. Long functions usually combine multiple concerns.

### Single responsibility

Each module has one primary concern. `extract.py` does extraction. `validate.py` does validation. Don't put validation helpers in `extract.py` because they're used during extraction.

### Pure functions where possible

Functions that don't touch DB or external services should be pure (same inputs always produce same outputs). Validators are a great example: `is_processable(text)` returns the same answer every time for the same text. This makes testing trivial.

## Comments

Code should be self-documenting through good naming. Comments only when WHY isn't obvious from the code.

```python
# Good - explains a non-obvious choice
# We use isalpha() for unicode-aware letter matching, since
# user feedback can be in any language.
alpha_count = sum(1 for c in text if c.isalpha() or c.isspace())

# Bad - restates the code
# Loop through each character in the text
for c in text:
    ...
```

No commented-out code in commits. Either delete it or commit it.

## Testing

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

- Every validator rejection rule has a test.
- Every service function has a happy path + at least one error path test.
- LLM calls always mocked. No real API calls in test runs.
- Use `pytest-asyncio` for async tests.
- Fixtures live in `conftest.py`.
- Each test is independent; no shared state across tests.
- Test names describe the behavior, not the implementation: `test_too_short_input_is_skipped` not `test_validate_returns_false`.
- Coverage target: meaningful tests on critical paths, not 100% line coverage.

## Style

Use `ruff` for linting and formatting. Configuration in `pyproject.toml`. Standard rules; no exotic enforcement.

Line length: 100 characters. Longer is fine for strings and URLs that don't break naturally.

No premature optimization. Write the clear version first. Profile before optimizing. Document any non-obvious optimization.

## Gotchas

Backend-specific things we've hit. Cross-cutting gotchas (nginx restart, fresh DB volume, `.env` access) live in the root `CLAUDE.md`.

- **nginx strips `/api/` before forwarding.** `nginx.conf` has `proxy_pass http://backend/;` (trailing slash) which replaces `/api/` with `/` before forwarding. So backend mounts routes at `/v1/...` and `/health` — NOT `/api/v1/...`. Don't add `prefix="/api"` when calling `app.include_router(v1_router)`. Symptom of getting it wrong: 404 on every `/api/v1/*` request.

- **SQLAlchemy `func.cast`: import the type, don't reach for `func.<Type>`.** Correct: `from sqlalchemy import Float, Integer; func.cast(col, Float)`. Wrong: `func.cast(col, func.Float)` → `AttributeError: 'Function' has no attribute 'Float'`. SQLAlchemy `func` is for SQL functions (count, sum, avg, lower, …), not types.

- **JSONB key access is Postgres-specific.** `Feedback.llm_metadata["latency_ms"].astext` (then `func.cast(..., Float)` for aggregates) works on asyncpg/Postgres. SQLite, MySQL, etc. would need `cast(json_extract(...))` or similar. We're Postgres-only by design — if that ever changes, every JSONB query in `feedback_repository.py` needs a rewrite.

- **`Base.metadata.create_all()` only creates missing tables.** It does NOT apply ALTER TABLE for column changes, type changes, or new NOT NULL columns. Phase 1-4 relies on `docker compose down -v` to drop the volume and let create_all rebuild fresh. Production graduation = Alembic migrations.

- **Anthropic SDK retries are off (`max_retries=0`).** Our `app/llm/client.py:get_client()` disables them deliberately; `call_with_retry()` owns the retry loop because we want the structured logs (`llm_timeout_retry`, `llm_rate_limit_retry`, `llm_5xx_retry`) and per-error-class backoff. If you re-init the SDK client, keep `max_retries=0`.

- **`tool_choice={"type": "tool", "name": "..."}` is required.** Without it, Claude can answer conversationally instead of calling our tool, and `extract.py` will raise `LLMSchemaError("No extract_insights tool_use in response")`. The forced tool name must match the tool entry in `tools=[...]` exactly — we use the `TOOL_NAME` constant in `extract.py` for both.

- **Sentiment trend window is anchored on today, walking back N-1 days.** `range(trend_days)` produces `[today - 13d, today]` — 14 buckets ending today inclusive. Easy to off-by-one this; symptom is "I posted feedback right now and it doesn't show in today's bucket."

- **`Field(default_factory=list)` on Pydantic ≠ `Field(default=[])`.** The latter is a shared mutable default. `default_factory=list` produces a fresh list per instance. Used in `ExtractionResult.action_items` and matters for any list/dict default.