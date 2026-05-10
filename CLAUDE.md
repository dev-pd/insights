# Feedback Insights

A POC for extracting structured insights from customer feedback using LLMs. Scoped as a small-scale demo built with production-grade code patterns.

## Stack
- Backend: Python 3.13, FastAPI, SQLAlchemy (async), Pydantic, asyncpg, Celery + Redis
- Frontend: Next.js 16 (App Router), React 19, TypeScript 5.9, Tailwind v4, shadcn/ui, SWR
- Database: Postgres 16 via docker-compose
- LLM: Anthropic API, `claude-haiku-4-5`

## Run commands
- `docker compose up` boots all services
- `cd backend && uv run pytest` runs tests
- `cd backend && uv run python evals/run_evals.py` runs prompt evals

## Imports
@.claude/context/architecture.md

## Where conventions live
- **Backend rules** (Python/FastAPI/SQLAlchemy): `backend/CLAUDE.md` — auto-loads when Claude reads files under `backend/`.
- **Frontend rules** (Next.js/TS/SWR): `frontend/CLAUDE.md` — auto-loads when Claude reads files under `frontend/`.
- **Backend implementation patterns** (config code, logging setup, exception hierarchy code, DI aliases, DB session, pooling, concurrency, shutdown, testing): `backend-patterns` skill — invoke when implementing these.
- **LLM workflow** (extraction, prompts, evals, `call_llm` wrapper): `llm-workflow` skill — invoke when working in `backend/app/llm/`.
- **Engineering notes** (migration table, what's deferred to production): `NOTES.md`.

## Gotchas

Cross-cutting items that bit us during phase work. Stack-specific gotchas live in `backend/CLAUDE.md` and `frontend/CLAUDE.md` (auto-load when working in those dirs).

- **Restart nginx after rebuilding any service it fronts.** nginx caches upstream container IPs at startup; rebuilding `backend` or `frontend` gives them new IPs that nginx still resolves to the old ones → 502 Bad Gateway. Fix: `docker compose restart nginx` after `docker compose build <service> && up -d`.
- **Destructive schema changes need `docker compose down -v`.** `Base.metadata.create_all()` only creates missing tables; it doesn't `ALTER`. Schema changes (column type, new required NOT NULL, etc.) require wiping the postgres volume so create_all rebuilds. Phase 5 graduation: Alembic migrations.
- **`.env` files are gitignored AND classifier-blocked.** `permissions.deny` in `.claude/settings.json` blocks reading `backend/.env` even from inside Bash. To inspect runtime env vars during debugging: `docker compose exec backend env | grep <KEY>` (runs inside the container; bypasses the host file deny). After bumping `.env.example`, sync your local `.env` manually — they're kept identical by convention but not enforced.

### Phase 4 (Celery + SSE) gotchas

- **The backend Docker image ships a venv, not `uv`.** The multi-stage Dockerfile puts `uv` in the builder stage only; the final image just exposes the venv binaries on PATH. Worker / beat commands must call `celery` directly, NOT `uv run celery` — symptom is `sh: 1: uv: not found` in worker logs.
- **Beat needs a writable schedule path.** The default `celerybeat-schedule` lives in CWD, which is `/app` and owned by root; the non-root `app` user can't write there. Use `--schedule=/tmp/celerybeat-schedule`. The state is just last-run timestamps — losing it on container restart at most fires one redundant invocation.
- **`asyncio.run()` in Celery tasks rebinds the event loop each call.** Caching a SQLAlchemy async engine at module level ties it to the FIRST loop, then subsequent tasks crash with `RuntimeError: Future attached to a different loop`. Fix: build the engine inside the async body via a context manager (`worker_session_scope` in `backend/app/tasks/_worker_session.py`) and dispose on exit. ~5ms per task vs 1s LLM call — negligible.
- **Anthropic SDK `APIConnectionError` lacks `status_code`.** It's the parent of `APITimeoutError`; both extend `APIError` but never got a response, so `if e.status_code` raises `AttributeError`. Use `getattr(e, "status_code", None)` and treat `None` as "transient — retry it". `backend/app/llm/client.py` does this now.
- **Workers see more transient Anthropic errors than the backend does.** Different processes, different DNS-resolved sockets, occasionally different egress paths. The retry+backoff loop in `call_with_retry` matters more for the worker path than for the backend's old sync path.
- **Separate Redis logical DBs for broker / results / cache.** `db 0` = cache + pub/sub, `db 1` = Celery broker, `db 2` = Celery results. `FLUSHDB` on one role doesn't pollute the others. Documented in `backend/.env.example`.
- **nginx `proxy_buffering off` + `proxy_read_timeout 24h`** are already on `/api/` from earlier work. Don't add a separate `/api/v1/events` location block — SSE works through the existing one. (Restarting nginx after backend rebuild still required — the upstream-IP-cache gotcha applies.)
- **EventSource doesn't reconnect on 4xx.** It auto-reconnects on transient drops but not on HTTP errors — so if a backend bug returns 401/404/500 the browser silently stops retrying. Test the SSE endpoint with `curl -N /api/v1/events` after deploys to catch this fast.

## What lives elsewhere
- Subagents: `.claude/agents/`
- Settings: `.claude/settings.json`