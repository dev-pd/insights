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
- `bash backend/scripts/stress_test.sh <N>` drives N synthetic items through the pipeline (CLI alternative to the dashboard "Add 100 feedbacks" button)

## Imports
@.claude/context/architecture.md

## Where conventions live
- **Backend rules** (Python/FastAPI/SQLAlchemy + the LLM module's call/retry/validate/schema/is_noise contract): `backend/CLAUDE.md` — auto-loads when reading files under `backend/`.
- **Frontend rules** (Next.js/TS/SWR): `frontend/CLAUDE.md` — auto-loads when reading files under `frontend/`.
- **Prompt iteration** (versioning, golden cases, eval gates): `prompt-engineering` skill — invoke when editing prompts or after an eval regression.
- **Reviewer surface**: `README.md` (setup), `NOTES.md` (context-engineering decisions), `PHASES.md` (build narrative), `CASE_STUDIES.md` (production-shaped incidents).

## Cross-cutting gotchas

Stack-specific gotchas live in `backend/CLAUDE.md` and `frontend/CLAUDE.md`. These bite across both:

- **Restart nginx after rebuilding any service it fronts.** nginx caches upstream container IPs at startup. Any recreate of `backend` or `frontend` — including `docker compose up --build` (rebuilt services get new container IPs while nginx stays untouched) and `docker compose up -d --force-recreate <service>` — leaves nginx resolving to the dead IP → `502 Bad Gateway` on `/api/*` while the container itself is healthy. Fix: `docker compose restart nginx`. Symptom check: `docker compose ps` shows nginx significantly older than the just-rebuilt service.
- **Destructive schema changes need `docker compose down -v`.** `Base.metadata.create_all()` only creates missing tables; it doesn't `ALTER`. Schema changes (column type, new required NOT NULL) require wiping the postgres volume so create_all rebuilds. Production graduation = Alembic.

## What lives elsewhere
- Sub-agents: `.claude/agents/` (edge-case-generator, prompt-evaluator)
- Settings: `.claude/settings.json` (committed denies) + `.claude/settings.local.json` (gitignored personal allows)
