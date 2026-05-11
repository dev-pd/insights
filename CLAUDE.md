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

- **Restart nginx after rebuilding any service it fronts.** nginx caches upstream container IPs at startup. Rebuilding `backend` or `frontend` gives them new IPs that nginx still resolves to the old ones → 502 Bad Gateway. Fix: `docker compose restart nginx` after `docker compose build <service> && up -d`.
- **Destructive schema changes need `docker compose down -v`.** `Base.metadata.create_all()` only creates missing tables; it doesn't `ALTER`. Schema changes (column type, new required NOT NULL) require wiping the postgres volume so create_all rebuilds. Production graduation = Alembic.
- **`.env` files are gitignored AND classifier-blocked.** `permissions.deny` in `.claude/settings.json` blocks reading `backend/.env` even from inside Bash. To inspect runtime env vars: `docker compose exec backend env | grep <KEY>` (runs inside the container; bypasses the host file deny). After bumping `.env.example`, sync your local `.env` manually.

## What lives elsewhere
- Sub-agents: `.claude/agents/` (edge-case-generator, prompt-evaluator)
- Settings: `.claude/settings.json` (committed denies) + `.claude/settings.local.json` (gitignored personal allows)
