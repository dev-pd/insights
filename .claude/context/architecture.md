# Architecture

This document describes the system shape: the API contract, folder layout, layered architecture, and async extraction flow.

## API contract

Source of truth: `backend/app/schemas.py` (Pydantic models).

| Method | Path | Purpose | Body / Query | Response |
|---|---|---|---|---|
| POST | `/v1/feedback` | Submit feedback (sync save, async extraction via Celery) | `{ texts: string[] }` | `{ received: int, processed: int, skipped: int, items: FeedbackOut[] }` |
| GET | `/v1/feedback` | List feedback with optional substring search | `?q=<substring>` | `{ items: FeedbackOut[] }` |
| GET | `/v1/stats` | Dashboard aggregations | none | `{ themes: [{name, count}], sentiment_dist: {...}, trend: [...], processing_count: int }` |
| GET | `/v1/events` | SSE stream for live updates | none | event stream (`text/event-stream`) of `feedback_updated` with `FeedbackOut` JSON payloads |
| GET | `/health` | Liveness — process is running (used by docker-compose healthcheck) | none | `{ status: "ok" }` |
| GET | `/ready` | Readiness — DB and Redis reachable | none | `{ status: "ok" }` or `503` with `{ database: bool, redis: bool }` |

### Versioning convention

Versioned API routes use URL-based versioning (`/v1/`). Operational routes (`/health`, `/ready`) are unversioned because they're contract-stable infrastructure endpoints. Bumping to `/v2/` is a future-compat path; this PoC ships only `v1`.

### Response envelope

All responses include `request_id` for tracing. On error, the response shape is:

```json
{
  "error": "error_type_slug",
  "detail": { "field_name": "human readable explanation" },
  "request_id": "uuid-string"
}
```

Status code mapping:
- `400` - input validation failed (Pydantic or business validator)
- `404` - resource not found
- `502` - LLM upstream failure (after retries exhausted)
- `503` - DB or worker unavailable
- `500` - unhandled internal error

### `FeedbackOut` shape

```typescript
{
  id: string,                       // UUID
  text: string,                     // raw input, never modified
  status: "processing" | "completed" | "failed" | "skipped",
  sentiment: "positive" | "neutral" | "negative" | null,
  themes: string[],                 // lowercase, 1-3 items, empty until completed
  action_items: string[],           // empty if none
  language: string | null,          // ISO 639-1 code, e.g. "en", "es"
  skip_reason: string | null,       // populated when skipped or failed
  created_at: string,               // ISO 8601 UTC
  updated_at: string                // ISO 8601 UTC, bumps on extraction completion
}
```

## OpenAPI metadata

`main.py` configures FastAPI with `title="Feedback Insights API"`, `version="0.1.0"`, and a brief description. `/docs` serves Swagger UI; `/redoc` serves ReDoc.

## Routing topology

Production-shaped docker-compose: an nginx container fronts both backend and frontend, routing `/api/*` to the backend (FastAPI :8000) and everything else to the frontend (Next.js `next start` :3000). The browser sees a single origin via nginx. Only the nginx container has a host port mapping (`FRONTEND_PORT`, default 8080); backend and frontend containers expose ports only on the internal docker network.

The frontend runs as a Node server, not a static export. This preserves the full Next.js feature surface — middleware, server components, server actions, API routes — so adding auth later (NextAuth.js, session middleware, protected server components) is a feature addition, not a deployment rewrite. Static export would force an architectural migration to add any of these.

## Folder structure

```
insights/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app factory, middleware, lifespan hooks
│   │   ├── config.py               # Pydantic Settings, env vars via get_settings()
│   │   ├── logging_config.py       # Structured JSON logging setup at startup
│   │   ├── middleware.py           # RequestIDMiddleware, GlobalExceptionHandler
│   │   ├── exceptions.py           # Custom exception hierarchy
│   │   ├── deps.py                 # FastAPI dependency providers
│   │   ├── db.py                   # Engine, Base, async session factory ONLY
│   │   ├── constants.py            # FeedbackStatus, SkipReason StrEnums
│   │   ├── schemas.py              # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── feedback.py         # POST /feedback, GET /feedback
│   │   │   ├── stats.py            # GET /stats
│   │   │   ├── events.py           # GET /events (SSE)
│   │   │   └── health.py           # GET /health, GET /ready
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── feedback.py         # Feedback SQLAlchemy model
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   └── feedback_repository.py # Data access for Feedback entity
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── feedback_service.py # Calls repositories, never SQLAlchemy directly
│   │   │   └── stats_service.py    # Aggregation queries (via repository)
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # Anthropic wrapper: retries, logging, timeout
│   │   │   ├── extract.py          # Extraction with structured tracing
│   │   │   ├── schema.py           # Pydantic ExtractionResult
│   │   │   ├── validate.py         # Pre-LLM input validation
│   │   │   └── prompts/
│   │   │       ├── __init__.py     # Exports ACTIVE_PROMPT, ACTIVE_VERSION
│   │   │       └── v1.py           # First prompt version (never edit, only add new versions)
│   │   └── tasks.py                # Celery task definitions (extract_and_update)
│   ├── evals/                      # Standalone scripts, not a Python package
│   │   ├── golden.json             # Hand-labeled test cases for prompt evaluation
│   │   └── run_evals.py            # Runner with --json mode for subagent
│   ├── tests/
│   │   ├── conftest.py             # Shared fixtures (test DB session, mocked LLM client)
│   │   ├── test_validate.py        # All validator rejection rules
│   │   ├── test_extract.py         # Mocked LLM, schema validation, retry behavior
│   │   └── test_feedback_service.py # Happy path + per-item failure isolation
│   ├── pyproject.toml              # Managed via uv
│   ├── Dockerfile
│   └── celery_worker.sh            # Worker entrypoint script
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Single-page UI composition
│   │   │   ├── layout.tsx          # Root layout, font setup
│   │   │   └── globals.css         # Tailwind imports
│   │   ├── components/
│   │   │   ├── PasteForm.tsx       # Textarea + submit
│   │   │   ├── FeedbackList.tsx    # Search input + scrollable card list
│   │   │   ├── FeedbackCard.tsx    # One feedback item with sentiment badge
│   │   │   ├── KpiCard.tsx         # One KPI tile
│   │   │   ├── ThemeFrequencyChart.tsx
│   │   │   └── SentimentTrendChart.tsx
│   │   ├── hooks/
│   │   │   └── useFeedbackStream.ts # SSE connection with smart lifecycle
│   │   └── lib/
│   │       ├── api/
│   │       │   ├── client.ts       # Typed fetch wrapper with error handling
│   │       │   ├── routes.ts       # API_ROUTES constants (no hardcoded paths)
│   │       │   └── types.ts        # FeedbackOut, FeedbackListResponse, StatsOut, etc.
│   │       ├── sentiment.ts        # SENTIMENT_STYLES, COLORS, LABELS maps
│   │       └── constants.ts        # UI_TIMINGS (debounce, polling, animations)
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js              # NO output: 'export' — runs as Node server (`next start`)
│   └── Dockerfile                  # Multi-stage Node build, runs `next start`
│
├── docker-compose.yml              # nginx + postgres + redis + backend + worker + frontend
├── nginx.conf                      # routes /api/* to backend, everything else to frontend
├── CLAUDE.md
├── NOTES.md
├── README.md
├── .env.example
├── .gitignore
└── .claude/
    ├── settings.json
    ├── agents/
    │   └── prompt-evaluator.md
    └── context/
        ├── architecture.md         # this file
        ├── backend-conventions.md
        ├── frontend-conventions.md
        ├── production-patterns.md
        └── llm-workflow.md
```

## Layered architecture (backend)

The backend follows strict layer boundaries. Each layer has a single responsibility and clear dependencies.

```
api/          → thin route handlers, Pydantic validation, status code mapping
  └──→ calls services/

services/     → business logic, orchestrates repositories + LLM
  └──→ calls repositories/ and llm/

repositories/ → data access, hides SQLAlchemy specifics from services
  └──→ uses db.py models and sessions

llm/          → LLM concerns, isolated from web layer
              → no knowledge of HTTP, DB, or repositories

models/       → SQLAlchemy entity definitions, one file per entity
              → imported by repositories
              → never import from services, api, or repositories

db.py         → SQLAlchemy engine, Base class, async session factory
              → no models, no queries, no business logic
```

### Boundary rules

These are non-negotiable. They keep the codebase navigable and the LLM module portable.

- `api/` **never** imports from `llm/` or `repositories/` directly. Always go through a service.
- `services/` **never** construct HTTP responses (return domain types; `api/` shapes the response).
- `services/` **never** import SQLAlchemy directly. All data access through a repository.
- `repositories/` are the only place SQLAlchemy queries live (besides `db.py` for engine setup).
- `llm/` knows nothing about HTTP, DB, or repositories. Pure bounded context.
- `db.py` exports engine, Base, and session factory ONLY. Models live in `models/`.
- `models/` contains SQLAlchemy entity definitions. One model per file. Models import only `Base` from `db.py`.
- `repositories/` import `Base`/session from `db.py` and entities from `models/`. They are the only consumers of `models/` outside of test code.

### Why these rules

**Separation of concerns.** When the bug is in extraction quality, you look only in `llm/`. When it's a routing issue, only in `api/`. When it's business logic, only in `services/`. No archaeology across layers.

**Portability.** The `llm/` folder is designed as a self-contained bounded context. If this PoC graduates to the Intryc codebase, the entire `llm/` module lifts as-is, regardless of the host's web framework, DB choice, or layering style. Only `api/` and `services/` need to be rewritten against host conventions.

**Testability.** Each layer can be tested in isolation. `services/` tests use mocked LLM clients and in-memory DBs. `llm/` tests don't need a web server.

**Why repositories.** Services contain business logic — validation, orchestration, error handling. Mixing data access into services means a single function knows about SQLAlchemy session lifecycles, query construction, AND business rules. Pulling data access into repositories gives services a clean, mockable contract: in tests, services can be exercised with an in-memory fake repository instead of mocking `session.execute()` calls. The cost is one extra file per entity; the benefit is tests that read like behavior specifications.

## Async extraction architecture

Submission and extraction are decoupled for responsive UX.

### Phase 1: synchronous submission (in-request)

When a user submits feedback via `POST /feedback`:

1. Pydantic validates the request body shape.
2. For each text in the batch, the service runs `is_processable()`.
3. If invalid: row saved with `status="skipped"`, `skip_reason` populated. No LLM call.
4. If valid: row saved with `status="processing"`. A Celery task is dispatched for extraction.
5. The endpoint returns immediately with all rows (mix of skipped and processing).

API response time is sub-100ms regardless of LLM latency. The user sees their feedback appear in the UI instantly.

### Phase 2: asynchronous extraction (background)

The Celery worker consumes `extract_and_update` tasks:

1. Loads the row from DB by `feedback_id`.
2. Calls `extract_insights(text)` (with retries, schema validation).
3. On success: updates row with `status="completed"`, populates `sentiment`, `themes`, `action_items`, `language`. Bumps `updated_at`.
4. On terminal failure: updates row with `status="failed"`, `skip_reason="llm_error"`. Bumps `updated_at`.

Each task has its own DB session via context manager. Per-task failures are isolated and logged.

### Background mechanism: Celery + Redis

For this demo, we use Celery with a Redis broker. The choice is deliberate even at small scale:

- **Durable task queue.** Worker can crash and restart without losing in-flight tasks.
- **Retry policies.** Celery's built-in retry decorator handles transient failures.
- **Horizontal scalability.** Adding more workers is a config change, not a code change.

For a non-Celery alternative, FastAPI's `BackgroundTasks` would also work. The dispatch boundary is the service function `extract_and_update(feedback_id, request_id)`, which is identical regardless of dispatch mechanism. Migration between mechanisms is a one-line change.

### Live updates to the frontend

Server-Sent Events (SSE) endpoint at `/events`:

- Frontend opens an `EventSource` connection only when at least one row has `status="processing"`.
- Closes connection automatically when all rows reach a terminal state.
- Backend polls DB every 1s for rows updated since the connection started.
- Pushes `feedback_updated` events with the full `FeedbackOut` payload.
- Server-side max stream duration: 5 minutes. Browser auto-reconnects on disconnect.

Frontend uses SWR's `mutate(routeKey)` to surgically update the row that changed, plus revalidates `/stats` to refresh KPI tiles and charts.

### State machine

```
                ┌──────────────┐
                │  (new entry) │
                └──────┬───────┘
                       │
                       ▼
                  validate?
                  /        \
            valid          invalid
              │               │
              ▼               ▼
        ┌──────────┐    ┌─────────┐
        │processing│    │ skipped │
        └─────┬────┘    └─────────┘
              │ Celery task runs
              ▼
         ┌────────┐    LLM error after retries    ┌────────┐
         │  LLM   │ ─────────────────────────────>│ failed │
         │  call  │                                └────────┘
         └────┬───┘
              │ success
              ▼
         ┌─────────┐
         │completed│
         └─────────┘
         
```

Terminal states: `completed`, `failed`, `skipped`. No state transitions out of these.