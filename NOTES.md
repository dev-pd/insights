# Engineering notes

Engineering decisions, tradeoffs, and what is deferred to a full-production graduation. Intended for reviewers reading the repo to understand *what's intentionally scoped down* vs *what's missing by accident*.

## Migration to full production

The patterns in this codebase are intentionally scaled for the PoC. A graduation path to full production:

| Concern | PoC approach | Production approach |
|---|---|---|
| DB migrations | Fresh schema on `docker compose up` | Alembic migrations |
| Error tracking | Logs only | Sentry / Datadog APM |
| Tracing | request_id in logs | OpenTelemetry across services |
| Metrics | None | Prometheus: LLM call counts, latencies, error rates |
| Secrets | `.env` file | AWS Secrets Manager / Vault |
| Auth | None (PoC) | API keys, JWT, request signing |
| Rate limiting | None | Per-client limits (e.g. slowapi) |
| Queue | Redis broker | Dedicated infrastructure with DLQ |
| Deploys | docker-compose | Kubernetes with rolling deploys |

Each is a clean addition without restructuring existing code, because the patterns above already enforce the right boundaries.

## The signal these patterns send

A senior reviewer reading this codebase should immediately see:

- Configuration is centralized, not scattered.
- Errors have a hierarchy and intentional handling.
- Logs are structured and traceable.
- Layers don't bleed into each other.
- Concurrency is bounded and resilient.
- Testing focuses on critical behavior, not coverage theater.
- The frontend handles real-world conditions (loading, errors, empty).

These aren't "nice to haves." They're the difference between code you ship and code you write.
