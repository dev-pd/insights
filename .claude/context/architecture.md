# Architecture

System shape for Feedback Insights — only the pieces that aren't redundantly documented elsewhere. For backend conventions read `backend/CLAUDE.md`; for frontend read `frontend/CLAUDE.md`.

## Routing topology

Production-shaped docker-compose stack:

```
browser → nginx :8080 → backend :8000  (path: /api/*)
                     → frontend :3000 (everything else)
                     → postgres :5432 (internal only)
                     → redis :6379    (internal only)
```

Only nginx exposes a host port (`FRONTEND_PORT`, default 8080). The browser sees one origin, so CORS is a defense-in-depth measure rather than a runtime requirement.

The frontend runs as a Node server (`next start`), not a static export. Preserves middleware, server components, server actions, API routes — adding auth later (NextAuth, protected routes) becomes a feature, not a deployment rewrite.

**nginx strips `/api/` before forwarding** (`proxy_pass http://backend/;` with trailing slash). Backend mounts routes at `/v1/...` and `/health`, NOT `/api/v1/...`. See backend/CLAUDE.md gotchas for the symptom-when-wrong.

## Where the API contract lives

Canonical source: `backend/app/schemas/` (Pydantic models, one file per concern). The OpenAPI doc at `/docs` is generated from these — when in doubt, read it. Don't trust hand-written API tables; they drift.

The error response envelope (returned by all routes on failure):

```json
{
  "error": "error_type_slug",
  "detail": { "field": "explanation" },
  "request_id": "uuid-string"
}
```

Status code mapping is in `backend/CLAUDE.md` § Custom exceptions.

## Layered architecture (backend)

Strict layer rules live in `backend/CLAUDE.md`. The one-line summary:

```
api/  →  services/  →  repositories/  →  models/ + db.py
              ↓
            llm/        (no HTTP, no DB, no repositories — pure bounded context)
```

Why this matters: `llm/` is portable. If the PoC graduates into a host codebase, the whole `llm/` module lifts as-is; only `api/` and `services/` get rewritten against host conventions.

## Async extraction flow

Two phases — the dashboard stays responsive because LLM work is decoupled.

**Phase 1: synchronous (in-request)**
1. `POST /v1/feedback/batch` accepts `{texts: list[str]}` (1-50 items).
2. Each text runs through the validator (`is_processable`).
3. Invalid → row saved as `skipped` with `skip_reason`. No LLM call.
4. Valid → row saved as `processing`, Celery task dispatched.
5. **Commit BEFORE `.delay()`** — see the dispatch-before-commit-race gotcha in CLAUDE.md.
6. Endpoint returns within ~100ms.

**Phase 2: asynchronous (Celery worker)**
1. `extract_feedback_task` loads the row.
2. Calls `extract_insights(text)` (retries + schema validation).
3. Success → row updated, status `completed`, `updated_at` bumped.
4. Terminal failure → row updated, status `failed`, `skip_reason="llm_error"`.
5. Worker publishes `events:feedback_update` + `events:stats_invalidate` to Redis pub/sub.

### State machine

```
                     ┌─→ skipped (terminal)
                     │
new → validate ──────┤
                     │
                     └─→ processing ─→ completed (terminal)
                                  └──→ failed    (terminal)
```

### Live updates

`GET /v1/events` is an SSE stream the frontend opens **only when at least one row is `processing`** — closes automatically when all rows reach a terminal state. Worker pub/sub events fan out to all connected clients.

## Background mechanism

Celery 5 + Redis broker. Topology:

| Redis logical DB | Purpose |
|---|---|
| `redis://redis:6379/0` | Summary cache + pub/sub channels (`events:*`) |
| `redis://redis:6379/1` | Celery broker |
| `redis://redis:6379/2` | Celery result backend |

Worker config rationale (see backend/CLAUDE.md § Async processing for full detail):
- `task_acks_late=True` + `task_reject_on_worker_lost=True` — crashed workers requeue mid-task.
- `worker_prefetch_multiplier=1` — fair distribution.
- Soft/hard time limits 120s/180s — comfortable for 30s LLM call × 3 retries.
- Retry budget from Settings (`celery_extract_max_retries=6`, `celery_extract_retry_backoff_max=120`) — sized to absorb a multi-minute Anthropic 429 burst.

**Beat schedule:** `regenerate-summary-hourly` (at :00) keeps the dashboard AI summary cache warm.

## See also

- `backend/CLAUDE.md` — backend conventions, gotchas, full Settings field list.
- `frontend/CLAUDE.md` — frontend conventions, SWR + SSE wiring.
- `.claude/skills/llm-workflow/SKILL.md` — extraction internals, prompt versioning, eval harness.
- `.claude/skills/prompt-engineering/SKILL.md` — prompt iteration workflow + golden case schema.
- `CASE_STUDIES.md` — production-shaped incidents (rate limits, event-loop binding, worker capacity).
- `NOTES.md` — migration table and what's deferred to production.
