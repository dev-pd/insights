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
(Add as discovered)

## What lives elsewhere
- Subagents: `.claude/agents/`
- Settings: `.claude/settings.json`