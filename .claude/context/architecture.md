# Architecture

System shape — only the cross-layer pieces. Stack-specific conventions live in `backend/CLAUDE.md` and `frontend/CLAUDE.md` (auto-load when reading those dirs).

## Routing topology

```
browser → nginx :8080 → backend :8000   (path: /api/*)
                     → frontend :3000   (everything else)
                     → postgres :5432   (internal only)
                     → redis :6379      (internal only)
```

Only nginx exposes a host port. The browser sees one origin so CORS is defense-in-depth, not a runtime requirement. **nginx strips `/api/`** before forwarding (`proxy_pass http://backend/;` with trailing slash) — backend mounts at `/v1/...` and `/health`, NOT `/api/v1/...`.

The frontend runs as a Node server (`next start`), not a static export. Preserves middleware / server components / API routes so adding auth later (NextAuth) is a feature, not a deployment rewrite.

## API contract envelope

Canonical schemas: `backend/app/schemas/` (Pydantic, one file per concern). OpenAPI doc at `/docs` is generated from these — when in doubt, read it. Don't trust hand-written API tables; they drift.

Error response (every route, every failure):

```json
{ "error": "ErrorClassName", "message": "...", "request_id": "uuid" }
```

Status mapping is in `backend/CLAUDE.md` § Custom exceptions.

## Async extraction flow

LLM work is decoupled so the dashboard stays responsive.

**In-request (~100ms):** `POST /v1/feedback/batch` validates each text → `validate_feedback()` returns `SkipReason | None`. Invalid rows persist as `skipped` with `skip_reason`. Valid rows persist as `processing`, then **commit BEFORE `task.delay()`** (orphan-row gotcha — see CASE_STUDIES.md). Endpoint returns immediately.

**Worker:** `extract_feedback_task` calls `extract_insights(text)` → records to `llm_usage` → branches on result:
- `is_noise=true` → status `skipped`, skip_reason `noise`
- `language != "en"` → status `skipped`, skip_reason `non_english_unsupported`
- otherwise → status `extracted` with sentiment/themes/action_items
- terminal LLM error → status `failed`, skip_reason `llm_validation_error`

Worker publishes `events:feedback_update` + `events:stats_invalidate` to Redis pub/sub for the SSE stream.

### State machine

```
                     ┌─→ skipped   (terminal: pre-LLM validator OR post-LLM noise/non-english)
                     │
new → validate ──────┤
                     │
                     └─→ processing ─→ extracted (terminal)
                                  └──→ failed    (terminal)
```

### Live updates

`GET /v1/events` is an SSE stream the frontend opens **only when `pending_count > 0`** — closes automatically when all rows reach a terminal state. Worker pub/sub events fan out to all connected clients.
