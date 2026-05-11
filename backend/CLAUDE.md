# Backend conventions

Project-specific rules for `backend/`. Generic Python conventions (type hints, naming, PEP 8 imports, no bare excepts) are assumed.

Stack: Python 3.13, `uv` (never `pip install`), `ruff`, `pytest`, FastAPI + SQLAlchemy async + asyncpg + Celery + redis-py + Anthropic SDK. Pinned versions in `uv.lock`.

## Layering rules

```
api/  →  services/  →  repositories/  →  models/ + db.py
              ↓
            llm/        (no HTTP, no DB, no repositories — bounded context)
```

- **`repositories/` is the ONLY place SQLAlchemy queries live.** Services and routes never import `sqlalchemy.*` directly.
- **`services/` owns business logic.** Stateless coordinators over repos + LLM module.
- **`models/` — one entity per file.** Indexes declared on the model so `Base.metadata.create_all()` produces them.
- **`llm/` is portable.** Plain text in / Pydantic out. Lifts cleanly into a host codebase.
- **`tasks/` — Celery body bridges to async via `asyncio.run`.** `worker_session.py` builds an engine per task (loop binding — see Case Study 7).

## LLM module (`app/llm/`)

Bounded context — no HTTP, no DB, plain text in / Pydantic out. Lifts cleanly into a host codebase. The folder structure above lists the files; this section documents the *why*.

**Tool use as extraction (not freeform JSON).** `extract.py` forces a structured response with `tool_choice={"type": "tool", "name": "extract_insights"}`. Three reasons: Anthropic constrains the tool input to match `input_schema` (freeform JSON has no such guarantee); no markdown-fence parsing; Pydantic round-trip is the single source of truth. Field `description` strings are read by Claude as part of the prompt — write them like instructions to a human annotator. Forced tool name must match the `tools=[...]` entry exactly (use the `TOOL_NAME` constant; mismatch → `LLMSchemaError("No extract_insights tool_use in response")`).

**`call_with_retry` owns the retry loop.** Anthropic SDK's built-in retries are disabled (`max_retries=0` on `AsyncAnthropic`) so we get structured per-error-class logs. Retries on `APITimeoutError`, `APIConnectionError`, 429, 5xx with exponential backoff + jitter. Does NOT retry on 4xx other than 429 — those are bugs, not transient. Maps to typed exceptions: `APITimeoutError → LLMTimeoutError`, 429 → `LLMRateLimitError`, 5xx → `LLMError`, schema mismatch → `LLMValidationError`. Bounded concurrency via `asyncio.Semaphore(settings.llm_concurrency_limit)`.

**Pre-LLM validation** (`validate_feedback()` returns `SkipReason | None`): length / alpha-ratio / profanity / empty / prompt-injection. See `app/constants.py:SkipReason` for the exhaustive list and `validate.py` for the rules.

Plus two POST-LLM skip reasons set by the worker after extraction:
- `NON_ENGLISH_UNSUPPORTED` — when `result.language != "en"` (app is English-only for now)
- `NOISE` — when `result.is_noise=true` (the LLM flagged the input as nonsense via the schema field; v1.7+ behavior). The other extracted fields are intentionally NOT persisted — dashboard treats it as pure noise rather than partial signal.

**Skipped vs failed:**
- `status="skipped"` — rejected pre-LLM by validator OR post-LLM by language/is_noise check. Always paired with `skip_reason`.
- `status="failed"` — passed validator, hit terminal LLM error. `skip_reason="llm_validation_error"` etc. — paid for the call.

For prompt iteration workflow (versioning, golden cases, eval gates, baseline updates): `.claude/skills/prompt-engineering/SKILL.md`.

## API endpoints — non-obvious behavior

Routes mount under `/v1/*` (the `v1_router`) plus unprefixed `/health` + `/ready`. Most behavior follows directly from the route signature + response schema; this section only documents the surprises.

- **`POST /v1/feedback/batch`**: per-item fault isolation — one item's exception is caught and persisted as FAILED so the batch keeps moving.
- **`GET /v1/stats`** — `today_delta.delta_pct` is `null` when `yesterday_count == 0` (UI renders `-` instead of infinity). Day-over-day windows anchor on `now` UTC, not midnight, so live submissions appear immediately. `count_in_window` uses half-open `[start, end)` intervals.
- **`GET /v1/summary`** — LLM failures are NOT cached: error path returns `cached=false, error="..."` with no Redis write so a bad Anthropic minute can't lock the dashboard. `summarize.py` does NOT force tool_use (we want prose, not JSON).

### LLM usage audit

Every successful LLM call writes a row to `llm_usage` (`app/models/llm_usage.py`) — canonical for cost + latency + per-prompt-version analytics. Pre-LLM skip paths (validator) don't record (no API call). **Post-LLM skip paths (NOISE, NON_ENGLISH_UNSUPPORTED) DO record** because the worker calls `record()` BEFORE the skip-branch check; we paid for the call.

### Prompt iteration

Workflow lives in `.claude/skills/prompt-engineering/SKILL.md` — invoke when editing anything under `app/llm/prompts/`. Two non-negotiable rules:

- **NEVER edit a released prompt version file.** Versions are immutable so `llm_usage.prompt_version` traces reproduce against the exact text on disk. New behavior = new file + `__init__.py` ACTIVE bump.
- **Rebuild BOTH backend AND worker images on ACTIVE bump.** Separate compose-built images. Symptom of forgetting: dashboard shows new version in eval reports but worker still runs old prompt on submitted feedback.

## No magic values

If a value could vary, repeat, or change with environment, it does NOT live inline in code.

| Type | Where it lives |
|---|---|
| Tunable thresholds (timeouts, retries, page sizes, model id, max_tokens) | `app/core/config.py` Settings |
| Status / skip-reason / enum-like strings | `app/constants.py` StrEnums |
| HTTP status codes | `fastapi.status.HTTP_*` |
| Secrets | Settings fields typed `SecretStr` |
| Repeated string literals (tool names, log event names) | Module-level `UPPER_SNAKE_CASE` in the owning file |
| API contract constraints (Pydantic `Field(min_length=, ...)`) | **Stay inline** in schemas — they define the contract |

Workflow for a new tunable: add field to `app/core/config.py:Settings` → add env var to `backend/.env.example` with matching default → read via `get_settings().<field>` (never `os.environ` directly). The Settings class is the source of truth for what exists and what defaults are; don't duplicate it here.

## Structured logging

JSON logs configured in `app/core/logging.py`, called once from `main.py` lifespan. **Always use `extra={...}` for context**, never f-strings — f-strings break the structured fields and lose the per-user `request_id` that propagates middleware → context var → log lines → Celery task args → LLM client metadata.

## Custom exceptions

`app/exceptions.py` is the hierarchy. `AppError` is the base; subclasses set `status_code` as a class attribute that `app_error_handler` reads. `SQLAlchemyError` subclasses get translated to `DatabaseError` (503) before the JSON envelope is built.

Layered handling: LLM client catches transient errors and retries → service catches `LLMError` and marks rows failed → global exception handler shapes the rest into `{error, message, request_id}` JSON.

## Database

- All queryable columns have explicit indexes in the model — `Feedback` has `status`, `created_at`, composite `(status, created_at)` for the SSE scan. Declared on the model so `Base.metadata.create_all()` produces them on bootstrap.
- One session per request via FastAPI dependency. Auto-commit on success, auto-rollback on exception. Sessions never escape the request context.
- Background tasks get their own session via `worker_session_scope` (built inside the async body — caching the engine at module level ties it to the FIRST asyncio.run() loop → `RuntimeError: Future attached to a different loop`).
- Async engine with `pool_size`, `max_overflow`, `pool_pre_ping=True` from Settings. Pre-ping prevents stale-connection errors after Postgres drops idle conns.

## Infrastructure boilerplate

- **Request body cap:** Starlette `Limits` middleware caps raw body at 1MB. Pydantic field-level caps are separate; this is the outer wall.
- **CORS:** `CORSMiddleware` installed with `allow_origins=[settings.frontend_origin]` as defense-in-depth — nginx fronting means same-origin at runtime. Never use `["*"]`.
- **Proxy headers:** uvicorn runs with `--proxy-headers --forwarded-allow-ips=*` because nginx is always in front. Real client IPs reach the request_id middleware (and any future per-IP rate limiting).
- **Graceful shutdown:** FastAPI lifespan handles it automatically. Celery worker uses soft/hard time limits 120s/180s set on `celery_app.conf` (not the CLI — keeps source-of-truth in one place).

## Async processing

Worker config lives in `app/tasks/celery_app.py` (read the file). Three Redis logical DBs on one instance: **db 0** = summary cache + pub/sub (`events:feedback_update`, `events:stats_invalidate`); **db 1** = Celery broker; **db 2** = result backend. Beat schedule: `regenerate-summary-hourly` at :00 keeps the summary cache warm.

**SSE** (`GET /v1/events`): loop polls pubsub with 1s timeout so client-disconnect + heartbeat are checked frequently. Heartbeat (SSE comment line) fires every `sse_heartbeat_interval_seconds` (default 30s) to survive nginx idle timeouts. Workers publish via sync redis; SSE endpoint subscribes via async — both target db 0. Publish failures swallowed at WARNING so a pub/sub outage doesn't poison the main flow.

## Testing

`backend/tests/` with pytest + pytest-asyncio. Run from `backend/` with `uv run pytest`. The image ships venv binaries only — `docker compose run backend pytest` won't find pytest. Coverage is intentionally narrow (the validator's noise rule is the only Tier-1 test today); the eval harness covers the LLM behavior layer.

## Gotchas

Backend-specific things we've hit. Cross-cutting gotchas (nginx restart, fresh DB volume, `.env` access) live in the root `CLAUDE.md`.

- **nginx strips `/api/` before forwarding** (`proxy_pass http://backend/;` with trailing slash). Backend mounts at `/v1/...` and `/health`, NOT `/api/v1/...`. Don't add `prefix="/api"` when including routers. Symptom: 404 on every `/api/v1/*` request.

- **SQLAlchemy `func.cast`: import the type, don't reach for `func.<Type>`.** Correct: `from sqlalchemy import Float; func.cast(col, Float)`. Wrong: `func.cast(col, func.Float)` → `AttributeError: 'Function' has no attribute 'Float'`.

- **JSONB key access is Postgres-specific.** `Feedback.llm_metadata["latency_ms"].astext` (then `func.cast(..., Float)` for aggregates) works on asyncpg/Postgres only. We're Postgres-only by design.

- **`Base.metadata.create_all()` only creates missing tables.** No ALTER TABLE for column changes. Schema changes require `docker compose down -v` to drop the volume and let create_all rebuild fresh. Production graduation = Alembic.

- **Anthropic SDK retries OFF (`max_retries=0`).** `client.py:get_client()` disables them deliberately; `call_with_retry()` owns the loop so we get structured per-error-class logs (`llm_timeout_retry`, `llm_rate_limit_retry`, `llm_5xx_retry`). Don't re-enable.

- **`APIConnectionError` lacks `status_code`.** It's a parent class of `APITimeoutError`; both extend `APIError` but never got a response. Use `getattr(e, "status_code", None)` and treat `None` as transient.

- **Loop identity, not `id()`, for the client cache.** `get_client()` caches `AsyncAnthropic` per loop OBJECT (`is`/`is not`), NOT `id(loop)`. CPython recycles addresses across GC'd loops, and `asyncio.run()` per Celery task creates+closes+GCs a loop each time → id-based cache never invalidates. See Case Study 7. The fix is in the comment; don't rewrite back to `id()`.

- **`tool_choice={"type": "tool", "name": "..."}` is required.** Without it Claude may answer conversationally and `extract.py` raises `LLMSchemaError("No extract_insights tool_use in response")`. Forced name must match the `tools=[...]` entry exactly — use the `TOOL_NAME` constant for both.

- **Sentiment trend window walks back N-1 days from today.** `range(trend_days)` produces `[today - 13d, today]` — 14 buckets ending today inclusive. Off-by-one symptom: "I posted feedback right now and today's bucket doesn't show it."

- **`Field(default_factory=list)` ≠ `Field(default=[])`.** Latter is a shared mutable default. Use `default_factory=list` for any list/dict default.

- **Dispatch-before-commit race in Celery.** Calling `task.delay()` before the request commits the row → worker beats the commit, queries DB, sees `not_found`, returns SUCCESS, row stays PROCESSING forever. Symptom: stress test of 20 items leaves 15-18 zombie rows. Fix: `await session.commit()` BEFORE `.delay()`. See CASE_STUDIES.md.
