# Backend conventions

Project-specific rules for `backend/`. Generic Python conventions (type hints, naming, PEP 8 imports, no bare excepts) are assumed — this file documents what's load-bearing for *this* codebase.

## Folder structure

```
backend/app/
├── api/
│   ├── deps.py                  Annotated DI aliases (SettingsDep, SessionDep, ...)
│   ├── health.py                /health, /ready
│   └── v1/router.py + routes/   /v1/feedback, /v1/stats, /v1/summary, /v1/events (SSE)
├── core/
│   ├── config.py                Pydantic Settings (singleton via @lru_cache)
│   └── logging.py               JSON logging setup
├── middleware/                  request_id, exceptions
├── models/                      Feedback, LlmUsage (one entity per file)
├── repositories/                CRUD + aggregations (only place SQLAlchemy queries live)
├── schemas/                     Pydantic request/response models (feedback, stats, summary, ...)
├── services/                    Business logic; never imports SQLAlchemy directly
├── llm/
│   ├── client.py                AsyncAnthropic + call_with_retry
│   ├── extract.py, summarize.py
│   ├── validate.py              Pre-LLM is_processable filter
│   ├── schema.py                ExtractionResult Pydantic
│   └── prompts/
│       ├── extraction/          v1.py, v1_1.py, v1_2.py (ACTIVE) + __init__ selector
│       └── summary/             v1.py, v1_1.py + __init__ selector
├── tasks/                       celery_app.py, feedback_tasks.py, _worker_session.py
├── constants.py                 FeedbackStatus, SkipReason (StrEnums)
├── db.py, exceptions.py, main.py

backend/tests/                   pytest + pytest-asyncio
backend/evals/                   Eval harness (run_evals.py, golden/, baseline.json, explore_edges.py)
backend/scripts/                 Ops scripts (stress_test.sh + DB recovery SQL)
```

## Tooling

Python 3.13, `uv` for package management (never `pip install` directly), `ruff` for lint/format, `pytest` for tests. Library versions pinned in `uv.lock`: FastAPI 0.136, Pydantic 2.13, SQLAlchemy 2.0.49 async, asyncpg, uvicorn 0.46, Anthropic SDK 0.100, Celery 5.6, redis-py 7.4.

## LLM module (`app/llm/`)

Bounded context — no HTTP, no DB, plain text in / Pydantic out. Lifts cleanly into a host codebase. Read the real files for code; this section documents the *why*.

```
app/llm/
├── client.py     AsyncAnthropic singleton + call_with_retry wrapper
├── extract.py    extract_insights() — tool-use extraction
├── summarize.py  generate_summary() — prose summary over many rows
├── schema.py     ExtractionResult Pydantic (sentiment, themes, action_items, language, is_noise)
├── validate.py   validate_feedback() — pre-LLM cheap-rejection filter
└── prompts/
    ├── extraction/  immutable versioned files + __init__ ACTIVE selector
    └── summary/     same layout
```

**Tool use as extraction (not freeform JSON).** `extract.py` forces a structured response with `tool_choice={"type": "tool", "name": "extract_insights"}`. Three reasons: Anthropic constrains the tool input to match `input_schema` (freeform JSON has no such guarantee); no markdown-fence parsing; Pydantic round-trip is the single source of truth. Field `description` strings are read by Claude as part of the prompt — write them like instructions to a human annotator. Forced tool name must match the `tools=[...]` entry exactly (use the `TOOL_NAME` constant; mismatch → `LLMSchemaError("No extract_insights tool_use in response")`).

**`call_with_retry` owns the retry loop.** Anthropic SDK's built-in retries are disabled (`max_retries=0` on `AsyncAnthropic`) so we get structured per-error-class logs. Retries on `APITimeoutError`, `APIConnectionError`, 429, 5xx with exponential backoff + jitter. Does NOT retry on 4xx other than 429 — those are bugs, not transient. Maps to typed exceptions: `APITimeoutError → LLMTimeoutError`, 429 → `LLMRateLimitError`, 5xx → `LLMError`, schema mismatch → `LLMValidationError`. Bounded concurrency via `asyncio.Semaphore(settings.llm_concurrency_limit)`.

**Pre-LLM validation** (`validate_feedback()` returns `SkipReason | None`):

| Trigger | SkipReason |
|---|---|
| Stripped length < `feedback_min_length` | `TOO_SHORT` |
| Stripped length > `feedback_max_length` | `TOO_LONG` |
| Alpha ratio < `feedback_min_alpha_ratio` | `GIBBERISH` |
| Empty / whitespace-only | `EMPTY` |
| `better_profanity` hit | `PROFANITY` |
| Regex match on override patterns ("ignore previous instructions", etc.) | `PROMPT_INJECTION` |

Plus two POST-LLM skip reasons set by the worker after extraction:
- `NON_ENGLISH_UNSUPPORTED` — when `result.language != "en"` (app is English-only for now)
- `NOISE` — when `result.is_noise=true` (the LLM flagged the input as nonsense via the schema field; v1.7+ behavior). The other extracted fields are intentionally NOT persisted — dashboard treats it as pure noise rather than partial signal.

**Skipped vs failed:**
- `status="skipped"` — rejected pre-LLM by validator OR post-LLM by language/is_noise check. Always paired with `skip_reason`.
- `status="failed"` — passed validator, hit terminal LLM error. `skip_reason="llm_validation_error"` etc. — paid for the call.

For prompt iteration workflow (versioning, golden cases, eval gates, baseline updates): `.claude/skills/prompt-engineering/SKILL.md`.

## API router composition

Sub-routers organized under `app/api/__init__.py`: `v1_router` gets `prefix="/v1"`, `ops_router` stays unprefixed. `main.py` mounts both.

### Batch feedback endpoint

`POST /v1/feedback/batch` accepts `{texts: list[str]}` (1-50 items). Each text validates → extracts or skips → persists. Per-item failures isolated: any unexpected exception during one item gets caught, logged, persisted as a FAILED row so the batch keeps moving.

Response: `{ items: [...], total: N, extracted: E, skipped: S, failed: F }` where `total = extracted + skipped + failed`.

In Phase 4 each text dispatches to Celery; the endpoint returns immediately with `processing` rows and SSE streams completion. `FeedbackService.create_feedback_batch` is the dispatch boundary — body changes, signature doesn't.

### Stats schema

`GET /v1/stats` returns a `StatsOut` shaped for the 6-KPI dashboard. Notable bits:
- `positive_pct`, `negative_pct` are `0.0` when `total_extracted == 0` (avoids div-by-zero on empty dashboard).
- `weekly_delta.delta_pct` is `null` when `last_week_count == 0` so the UI renders `-` instead of infinity.
- `weekly_delta` windows anchor on `now` (UTC), not midnight, so live submissions appear immediately.
- `top_themes` and `sentiment_trend` are tunable via `stats_theme_window_days` / `stats_top_themes_limit` / `stats_trend_days` Settings.
- `count_in_window` uses half-open intervals `[start, end)` so back-to-back windows don't double-count the boundary instant.

### Summary endpoints

`GET /v1/summary` reads from Redis cache (key `summary:current`, TTL = `summary_cache_ttl_seconds`, default 3600). `POST /v1/summary/refresh` deletes the key, regenerates, writes back.

- **LLM failures are NOT cached.** A bad minute at Anthropic shouldn't lock the dashboard into "broken" for a full TTL — error path returns `cached=false`, `error="..."`, no Redis write.
- **`summary_min_feedback_items` floor (default 3):** below this, `generate_summary` short-circuits with a static message — model would otherwise produce useless output on a thin sample.
- **Separate prompt family `summary_v1`:** different concern from per-item extraction; iterates independently. Past prompt versions stay in the tree forever so traces from `prompt_version` metadata reproduce.
- **No tool_use forcing for summary:** we want prose, not JSON. `extract.py` forces it because downstream reads structured fields; `summarize.py` reads text content.
- **Active summary prompt (`summary/v1.2`) targets 380-500 chars** in a fixed three-part structure (sentiment-direction opening with named praises + mention counts → "However" pivot to urgent issues with counts → priority callout). v1.1 had a loose "50-80 words max" guidance and outputs varied 180-550 chars, which reflowed the dashboard card unpredictably. The character target keeps the SummaryWidget card from layout-jumping.

### LLM usage audit

Every successful LLM call writes one row to `llm_usage` (`app/models/llm_usage.py`). Single source of truth for cost + latency + per-version analytics. Columns: `call_type` (`"extraction" | "summary"`), `model`, `input_tokens`, `output_tokens`, `latency_ms`, `prompt_version`, `feedback_id` (FK, nullable — extraction only). The dashboard doesn't render token/latency tiles in the current 5-KPI layout (those got cut as operator-facing telemetry), but the table is still the canonical source for any cost/latency reporting and gets read by the eval workflow when comparing prompt versions.

Skipped/failed paths don't record — no successful response → no tokens to capture.

### Prompt iteration: the agent loop

Hardening the extraction prompt happens via a three-role pipeline orchestrated through the filesystem (no agent-to-agent IPC — files are the bus):

```
edge-case-generator  →  golden/extraction.candidates.jsonl
prompt-evaluator     →  reports/<UTC>-<version>.json
main Claude + human  →  diagnose, refine, ship
```

The full flow (which files get touched when, what the per-round commit looks like) lives in `.claude/skills/prompt-engineering/SKILL.md` § "The human-minimal loop". When touching anything under `app/llm/prompts/` invoke that skill. Key rules:

- **NEVER edit a released prompt version file** (`extraction/v1.py`, `v1_1.py`, etc.). Versions are immutable so production traces from `llm_usage.prompt_version` reproduce against the exact text on disk forever. New behavior = new version file + `__init__.py` ACTIVE bump.
- **Rebuild BOTH backend AND worker images** when bumping ACTIVE — they have separate compose-built images even though both build from `./backend`. Symptom of forgetting: dashboard shows new version in eval reports but worker still runs old prompt on submitted feedback.
- **Per-round commits land everything together**: new version file + ACTIVE bump + new/refined goldens + `baseline.json` (`observed_at_baseline` + raised `thresholds`) + the before/after report files + `NOTES.md` section-2 line. Commit message body MUST include metric deltas — that's the audit signal.

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

### Currently defined Settings (May 2026)

For reference when wiring new code — pick the existing field, don't redefine:

- **External:** `anthropic_api_key`, `database_url`, `db_pool_size`, `db_max_overflow`, `redis_url`, `redis_max_connections`, `redis_socket_connect_timeout_seconds`
- **LLM:** `llm_model`, `llm_max_tokens`, `llm_timeout_seconds`, `llm_max_retries`, `llm_retry_base_delay_seconds`, `llm_concurrency_limit`
- **Celery retries:** `celery_extract_max_retries` (default 6), `celery_extract_retry_backoff_max` (default 120) — sized to absorb a multi-minute Anthropic 429 burst
- **Validation:** `feedback_min_length`, `feedback_max_length`, `feedback_min_alpha_ratio`
- **API limits:** `feedback_request_max_length`, `feedback_list_default_limit`
- **Stats:** `stats_trend_days`, `stats_theme_window_days`, `stats_top_themes_limit`
- **Summary:** `summary_cache_ttl_seconds`, `summary_min_feedback_items`
- **SSE:** `sse_poll_interval_seconds`, `sse_max_stream_duration_minutes`, `sse_heartbeat_interval_seconds`
- **Stress test:** `stress_test_max_count` (default 200 — hard cap so a typo can't burn real budget)

Workflow for a new tunable: add field to Settings → add env var to `backend/.env.example` with matching default → read via `get_settings().<field>` (never `os.environ` directly). No backstop module constant.

## Structured logging

JSON logs configured in `app/core/logging.py`, called once from `main.py` lifespan. **Always use `extra={...}` for context**, never f-strings (`logger.info(f"...{id}...")` breaks the structured fields).

Required fields by event:

| Event | Level | Fields |
|---|---|---|
| Endpoint entry | INFO | event, path, method, request_id |
| LLM call start/complete | INFO | event, prompt_version, latency_ms, input/output_tokens, request_id |
| LLM call failed | WARNING/ERROR | event, error_type, attempt, request_id |
| Feedback skipped | INFO | event, skip_reason, feedback_id, request_id |
| Caught exception | ERROR | full traceback via `logger.exception()`, request_id |

`request_id` propagates via middleware → context var → log lines → Celery task args → LLM client metadata. Every log line for one user action carries the same id.

## Custom exceptions

Hierarchy in `app/exceptions.py`:

```
AppError
├── InputValidationError
├── LLMError
│   ├── LLMTimeoutError
│   ├── LLMValidationError
│   └── LLMRateLimitError
└── DatabaseError
```

Status mapping in middleware: `InputValidationError → 400`, `LLMError → 502`, `DatabaseError → 503`, else 500. `SQLAlchemyError` subclasses get translated to `DatabaseError` before mapping. Layered handling: LLM client catches transient errors and retries → service catches `LLMError` and marks rows failed → global exception handler shapes the rest into `{error, detail, request_id}` JSON.

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

## Async processing (Phase 4)

Feedback extraction runs through Celery. `POST /v1/feedback/batch` persists rows as `processing` then dispatches; worker picks up task, extracts, updates row, publishes to Redis pub/sub for the SSE stream.

Redis topology (one instance, three logical DBs):
- `db 0` — summary cache + pub/sub channels (`events:feedback_update`, `events:stats_invalidate`)
- `db 1` — Celery broker
- `db 2` — Celery result backend

Worker config in `app/tasks/celery_app.py`:
- `task_acks_late=True` + `task_reject_on_worker_lost=True` — crashed workers requeue mid-task
- `worker_prefetch_multiplier=1` — fair distribution
- JSON-only serialization
- `task_soft_time_limit` / `task_time_limit` from Settings

Retry policy on `extract_feedback_task`: `autoretry_for=(LLMError, TimeoutError, ConnectionError)`, exponential backoff with jitter, budget from Settings (default 6 retries × 120s backoff_max).

Beat schedule: `regenerate-summary-hourly` at :00 keeps the dashboard summary cache warm.

### SSE endpoint

`GET /v1/events` streams `text/event-stream`. Loop polls pubsub with 1s timeout so we can check client-disconnect + heartbeat-due frequently. Heartbeat (SSE comment) fires every `sse_heartbeat_interval_seconds` (default 30s) to keep the connection alive through nginx idle timeouts.

Events: `connected` (one-shot on subscribe), `feedback_update` (per worker completion), `stats_invalidate` (per worker completion).

Workers use sync redis (`publish_feedback_event_sync`); SSE endpoint uses async `pubsub.subscribe`. Both target db 0. Helpers swallow publish failures at WARNING so a pub/sub outage never poisons the main flow.

## Testing

`backend/tests/` with pytest + pytest-asyncio. Fixtures (mocked LLM client, test DB session, parameterized invalid/valid texts) in `conftest.py`. LLM calls always mocked — no real API calls in tests. Test names describe behavior (`test_too_short_input_is_skipped`), not implementation. Coverage target: meaningful tests on critical paths, not 100%.

## Gotchas

Backend-specific things we've hit. Cross-cutting gotchas (nginx restart, fresh DB volume, `.env` access) live in the root `CLAUDE.md`.

- **nginx strips `/api/` before forwarding** (`proxy_pass http://backend/;` with trailing slash). Backend mounts at `/v1/...` and `/health`, NOT `/api/v1/...`. Don't add `prefix="/api"` when including routers. Symptom: 404 on every `/api/v1/*` request.

- **SQLAlchemy `func.cast`: import the type, don't reach for `func.<Type>`.** Correct: `from sqlalchemy import Float; func.cast(col, Float)`. Wrong: `func.cast(col, func.Float)` → `AttributeError: 'Function' has no attribute 'Float'`.

- **JSONB key access is Postgres-specific.** `Feedback.llm_metadata["latency_ms"].astext` (then `func.cast(..., Float)` for aggregates) works on asyncpg/Postgres only. We're Postgres-only by design.

- **`Base.metadata.create_all()` only creates missing tables.** No ALTER TABLE for column changes. Phase 1-4 relies on `docker compose down -v` to drop the volume and let create_all rebuild fresh. Production graduation = Alembic.

- **Anthropic SDK retries OFF (`max_retries=0`).** `client.py:get_client()` disables them deliberately; `call_with_retry()` owns the loop so we get structured per-error-class logs (`llm_timeout_retry`, `llm_rate_limit_retry`, `llm_5xx_retry`). Don't re-enable.

- **`APIConnectionError` lacks `status_code`.** It's a parent class of `APITimeoutError`; both extend `APIError` but never got a response. Use `getattr(e, "status_code", None)` and treat `None` as transient.

- **Loop identity, not `id()`, for the client cache.** `get_client()` caches `AsyncAnthropic` per loop OBJECT (`is`/`is not`), NOT `id(loop)`. CPython recycles addresses across GC'd loops, and `asyncio.run()` per Celery task creates+closes+GCs a loop each time → id-based cache never invalidates. See Case Study 7. The fix is in the comment; don't rewrite back to `id()`.

- **`tool_choice={"type": "tool", "name": "..."}` is required.** Without it Claude may answer conversationally and `extract.py` raises `LLMSchemaError("No extract_insights tool_use in response")`. Forced name must match the `tools=[...]` entry exactly — use the `TOOL_NAME` constant for both.

- **Sentiment trend window walks back N-1 days from today.** `range(trend_days)` produces `[today - 13d, today]` — 14 buckets ending today inclusive. Off-by-one symptom: "I posted feedback right now and today's bucket doesn't show it."

- **`Field(default_factory=list)` ≠ `Field(default=[])`.** Latter is a shared mutable default. Use `default_factory=list` for any list/dict default.

- **Dispatch-before-commit race in Celery.** Calling `task.delay()` before the request commits the row → worker beats the commit, queries DB, sees `not_found`, returns SUCCESS, row stays PROCESSING forever. Symptom: stress test of 20 items leaves 15-18 zombie rows. Fix: `await session.commit()` BEFORE `.delay()`. See CASE_STUDIES.md.
