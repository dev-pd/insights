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

## What lives elsewhere
- Subagents: `.claude/agents/`
- Settings: `.claude/settings.json`