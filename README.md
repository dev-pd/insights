# Feedback Insights

Local LLM-powered customer feedback analyzer. FastAPI backend, Next.js frontend, Postgres + Redis + Celery for async extraction. nginx in front of both services for single-origin routing.

## Setup

1. Copy env templates:

   ```
   cp backend/.env.example backend/.env
   ```

2. Add your Anthropic API key to `backend/.env`:

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Run the stack:

   ```
   docker compose up
   ```

4. Open http://localhost:8080

The first run will pull images, build containers, and run migrations. Subsequent runs are faster. Postgres data persists in a named docker volume; remove it with `docker compose down -v` if you want a fresh DB.

## Architecture

See `.claude/context/architecture.md` for the full architecture, API contract, and folder layout.

## Notes for reviewers

See `NOTES.md` for engineering decisions, tradeoffs, and what is deferred to a full-production graduation.
