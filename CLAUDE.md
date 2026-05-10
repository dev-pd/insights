# Feedback Insights

A POC for extracting structured insights from customer feedback using LLMs. Scoped as a small-scale demo built with production-grade code patterns.

## Stack
- Backend: Python 3.11, FastAPI, SQLAlchemy (async), Pydantic, asyncpg, Celery + Redis
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui, recharts, SWR
- Database: Postgres 16 via docker-compose
- LLM: Anthropic API, `claude-haiku-4-5`

## Run commands
- `docker compose up` boots all services
- `cd backend && uv run pytest` runs tests
- `cd backend && uv run python evals/run_evals.py` runs prompt evals

## Imports
@.claude/context/architecture.md
@.claude/context/backend-conventions.md
@.claude/context/frontend-conventions.md
@.claude/context/production-patterns.md
@.claude/context/llm-workflow.md

## Gotchas
(Add as discovered)

## What lives elsewhere
- Subagents: `.claude/agents/`
- Settings: `.claude/settings.json`