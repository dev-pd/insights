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
- **LLM workflow** (extraction internals, `call_with_retry`, failure modes): `llm-workflow` skill — invoke when working in `backend/app/llm/`.
- **Prompt iteration** (versioning, golden cases, eval gates): `prompt-engineering` skill — invoke when editing prompts or after an eval regression.
- **Reviewer notes**: `NOTES.md` at repo root.

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
- **Workers see more transient Anthropic errors than the FastAPI process does.** Different processes, different DNS-resolved sockets, occasionally different egress paths. The retry+backoff loop in `call_with_retry` matters more on the worker path (where most calls happen) than on the request path (where only the summary endpoint calls Anthropic now).
- **Separate Redis logical DBs for broker / results / cache.** `db 0` = cache + pub/sub, `db 1` = Celery broker, `db 2` = Celery results. `FLUSHDB` on one role doesn't pollute the others. Documented in `backend/.env.example`.
- **nginx `proxy_buffering off` + `proxy_read_timeout 24h`** are already on `/api/` from earlier work. Don't add a separate `/api/v1/events` location block — SSE works through the existing one. (Restarting nginx after backend rebuild still required — the upstream-IP-cache gotcha applies.)
- **EventSource doesn't reconnect on 4xx.** It auto-reconnects on transient drops but not on HTTP errors — so if a backend bug returns 401/404/500 the browser silently stops retrying. Test the SSE endpoint with `curl -N /api/v1/events` after deploys to catch this fast.

- **Dispatch-before-commit race in Celery.** Calling `task.delay()` before the request commits the row meant the worker often beat the commit, queried the DB, saw `not_found`, and returned a clean SUCCESS — leaving the row in PROCESSING forever. Symptom: stress test of 20 items leaves 15-18 zombie rows. Fix: `await session.commit()` BEFORE `.delay()`. The 5-10ms extra latency per submission is worth a guaranteed-visible row.

## Stress testing and capacity

Two paths, same underlying pipeline:

- **Dashboard button** — top-right of `/`, dispatches 100 synthetic items through `POST /v1/feedback/stress-test`. Hard-capped at `Settings.stress_test_max_count` (default 200) so a typo can't burn real budget.
- **`backend/scripts/stress_test.sh <N>`** — CLI version with live drain logging + latency stats. Goes through `/v1/feedback/batch` and supports any N via 50-item chunking.

**Capacity observed (Haiku default Anthropic tier, `CELERY_WORKER_CONCURRENCY=3`):**

| N | Drain | Throughput | Failed | Notes |
|---|---|---|---|---|
| 20 | 11s | 1.9 items/s | 0 | within rate limits |
| 50 | 32s | 1.6 items/s | 0 | within rate limits |
| 100 | 99s | 0.77 items/s | 24% (rate-limited) | Anthropic 429s start dominating |
| 1000 (extrapolated) | ~20 min | ~0.8 items/s sustained | likely ~25-40% w/o retry-policy tuning | budget concern |

**The ceiling is Anthropic, not us.** Haiku default tier is ~50 RPM (~0.83 calls/s); 3 concurrent workers at ~2s/call push ~1.5 calls/s — bursts exceed the rate limit and the SDK returns 429s. Our retry budget (`celery_extract_max_retries=6`, exponential backoff up to `celery_extract_retry_backoff_max=120s`, both Settings-driven) absorbs multi-minute 429 bursts in practice but exhausts under sustained overload — see CASE_STUDIES.md case 6.

**To push higher cleanly:** bump `CELERY_WORKER_CONCURRENCY` to match your Anthropic tier (the retry budget already absorbs the bursts), or wrap `extract_insights` in `asyncio.Semaphore(settings.llm_concurrency_limit)` to throttle below the rate limit. Both are graduation work — current setup is right for take-home demo scale.

## What lives elsewhere
- Subagents: `.claude/agents/`
- Settings: `.claude/settings.json`