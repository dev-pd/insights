# Feedback Insights

Local LLM-powered customer feedback analyzer. FastAPI backend, Next.js frontend, Postgres + Redis + Celery for async extraction. nginx in front of both services for single-origin routing.

## Setup

Prerequisites: Docker Desktop (or compatible docker + docker compose) running locally.

1. Copy the env template:

   ```
   cp backend/.env.example backend/.env
   ```

2. Add your Anthropic API key to `backend/.env`:

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Boot the stack:

   ```
   docker compose up
   ```

4. Open http://localhost:8080

First run pulls images, builds containers, and initializes the schema via SQLAlchemy `create_all()` on the postgres volume. Subsequent runs are faster. To wipe the DB: `docker compose down -v`.

## What you'll see

- **`/` dashboard** — 6 KPI tiles (Total feedback / Positive / Neutral / Negative / Today / Total tokens), an AI summary widget, a top-themes chart, and a sentiment-over-time chart. Empty on first run.
- **`/add`** — paste one feedback at a time or a batch (blank-line- or newline-separated, 1–50 items). The extraction runs asynchronously; rows appear immediately as `processing` and update via SSE as the worker completes them.
- **`/feedback`** — searchable list of all feedback with their extracted sentiment, themes, and action items.

Paste 2–3 realistic feedback items on `/add` and watch them flow through. Drain takes ~3-5s per item on Haiku.

## Running the eval harness

The eval harness scores the active extraction prompt against ~50 hand-curated golden cases (current count in `backend/evals/baseline.json`). Used as a CI gate and as part of the iteration workflow when bumping prompt versions.

```
docker compose run --rm \
  -v "$(pwd)/backend/evals:/app/evals:ro" \
  backend python /app/evals/run_evals.py --check
```

Exits 0 if all metrics clear the floors in `backend/evals/baseline.json`, 1 if any regressed.

## Where things live

- **Application code**: `backend/app/` and `frontend/src/`. Architecture overview in `.claude/context/architecture.md`.
- **Claude Code harness** (the take-home's primary signal): `.claude/` + the per-directory CLAUDE.md files. Reviewer notes in `NOTES.md` at the repo root.
- **Production-shaped incidents we hit** (rate limits, event-loop binding bug, dispatch-before-commit race): `CASE_STUDIES.md`.

## Notes for reviewers

Read `NOTES.md` for the context-engineering decisions, what didn't work, and what I'd add if this were long-lived.
