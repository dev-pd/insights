---
name: backend-patterns
description: Implementation snippets for backend/app/ that aren't already in backend/CLAUDE.md — Settings boilerplate, async session lifecycle, connection pooling args, bounded gather, Celery shutdown timings. Invoke when wiring new infrastructure code (config, DB engine, worker entrypoints, concurrency primitives).
---

# Backend implementation patterns

Code references for the FastAPI backend. Rules and conventions live in `backend/CLAUDE.md` — this file only documents implementation snippets that aren't trivially findable in the real code.

## Configuration

`app/core/config.py` uses Pydantic Settings with a cached singleton. The real Settings class has ~40 fields (LLM, validation, stats, SSE, Celery, Redis); read it directly. The pattern shape:

```python
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: SecretStr           # never str — keeps it out of __repr__
    database_url: str
    llm_model: str = "claude-haiku-4-5"
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    # ...

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Key rules:
- One Settings class — no scattered `os.environ.get()` in business code.
- Secrets typed as `SecretStr` so they stay out of logs/repr.
- `@lru_cache` so `.env` is parsed once per process.
- Inject via `Depends(get_settings)` in routes; never import the singleton inside service logic.
- When adding a new tunable, also update `backend/.env.example` with the same default + a comment (see backend/CLAUDE.md § No magic values).

## Logging setup

```python
# app/core/logging.py
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

Called once from `app/main.py`'s lifespan. The "what to log" event table and `extra=` discipline live in backend/CLAUDE.md.

## DI aliases

`app/api/deps.py` exposes `Annotated` aliases so route signatures stay readable:

```python
SettingsDep   = Annotated[Settings, Depends(get_settings)]
SessionDep    = Annotated[AsyncSession, Depends(get_session)]
RequestIdDep  = Annotated[str, Depends(get_request_id)]
LLMClientDep  = Annotated[AsyncAnthropic, Depends(get_llm_client)]
```

Use these in handlers instead of writing `Depends(...)` inline. Routes become declarative.

## DB session lifecycle

```python
# app/db.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,        # default 10
    max_overflow=settings.db_max_overflow,  # default 20
    pool_pre_ping=True,                     # SELECT 1 before checkout
)
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

Rationale:
- `pool_pre_ping=True` catches stale connections after Postgres drops idles (real failure mode for long-lived workers).
- `expire_on_commit=False` — objects stay usable after commit; avoids surprise lazy-load round trips.
- Auto-commit/rollback in the DI provider means handlers never write `session.commit()` themselves.

Worker tasks need their own session per task (not the request-scoped one) — see `app/tasks/_worker_session.py` for the `worker_session_scope` context manager. **Don't cache the engine across tasks**: `asyncio.run()` per Celery task rebinds the loop, and a cached engine ties to the FIRST loop → `RuntimeError: Future attached to a different loop`.

## Bounded concurrency

For batches that call external services (LLM, third-party HTTP), wrap with a Semaphore from Settings:

```python
async def process_batch(texts: list[str]) -> list[ProcessResult]:
    semaphore = asyncio.Semaphore(get_settings().llm_concurrency_limit)

    async def with_limit(text: str) -> ProcessResult:
        async with semaphore:
            return await process_one(text)

    return await asyncio.gather(
        *[with_limit(t) for t in texts],
        return_exceptions=True,   # never let one failure abort the batch
    )
```

`return_exceptions=True` is non-negotiable for batch work. Always partition `[Exception, ...]` from `[result, ...]` after.

## Graceful shutdown

**FastAPI**: lifespan protocol handles it automatically. On `SIGTERM`, uvicorn stops accepting new connections, waits for in-flight requests, exits.

**Celery worker** needs explicit time limits set on the Celery app (not the CLI — keeps source-of-truth in `app/tasks/celery_app.py`):

```python
celery_app.conf.update(
    task_soft_time_limit=120,  # raises SoftTimeLimitExceeded inside the task
    task_time_limit=180,       # hard kill
)
```

120s soft / 180s hard is comfortable for 30s LLM call × 3 retries. On `SIGTERM`, Celery finishes the in-flight task before exiting (warm shutdown).

**Workers must call `celery` directly, not `uv run celery`** — the multi-stage Dockerfile drops `uv` from the final image. See `docker-compose.yml`'s worker entrypoint.

## Repository pattern

All SQLAlchemy queries live in `app/repositories/`, one class per aggregate root. Methods are async, return domain types (the SQLAlchemy model), never raise `HTTPException`. The shape:

```python
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
        await self.session.flush()  # assigns ID without committing
        return feedback
```

Services receive repositories via FastAPI DI (see `app/api/deps.py:get_feedback_repository`). Services never import SQLAlchemy or `db.py` directly.

## See also

- `backend/CLAUDE.md` — every rule, naming convention, error-handling layering, testing discipline. This skill is the *snippet appendix*, not the *rule book*.
- `.claude/skills/llm-workflow/SKILL.md` — LLM-specific patterns (client wrapper, retries, eval harness).
- `.claude/context/architecture.md` — system topology and the async extraction flow.
