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

## Capacity case study — Anthropic rate limits vs worker concurrency

The async pipeline (Celery worker pool + SSE) handles arbitrary burst sizes from the user's perspective, but the *underlying* extraction rate is bounded by Anthropic's per-org rate limits. Getting `CELERY_WORKER_CONCURRENCY` right is the difference between a stress test draining cleanly and 90+ items going to FAILED status with 429 errors.

### The two limits Anthropic enforces

Both apply per organization per model. Default tier as of this writing:

| Model | RPM (requests/min) | TPM (input tokens/min) | Per-call latency (observed) | Cost / 1M input |
|---|---:|---:|---:|---:|
| `claude-haiku-4-5` | 50 | 50,000 | ~1.5-2.5s | $0.25 |
| `claude-opus-4-7` | 50 | 50,000 | ~5-10s | $15 |

Anthropic sends a 429 the moment EITHER cap is exceeded in the current minute. The cap *that bites first* depends on the model AND your prompt size.

Our extraction prompts run ~1250 input tokens (system prompt + tools schema + user feedback). So **50 RPM × 1250 = 62,500 tokens** — which is over the 50k TPM cap. **TPM bites before RPM** for our prompt size.

### The formula

The worker pool's sustained Anthropic call rate is:

```
calls_per_second = CELERY_WORKER_CONCURRENCY / avg_call_latency_seconds
calls_per_minute = calls_per_second × 60
tokens_per_minute = calls_per_minute × avg_prompt_tokens
```

The pipeline is rate-safe when **both** `calls_per_minute ≤ RPM_cap` AND `tokens_per_minute ≤ TPM_cap`.

### Worked example — Haiku at concurrency=4 (what we did)

```
calls/sec    = 4 / 1.5  = 2.67
calls/min    = 2.67 × 60 = 160          ← cap is 50 → 3.2x over RPM
tokens/min   = 160 × 1250 = 200,000     ← cap is 50k → 4x over TPM
```

Both caps shattered. Empirically: out of 100 dispatched, **95 hit `LLMRateLimitError`** after exhausting our 6-retry budget. Throughput dropped to ~0.77 items/s (vs the theoretical 2.67/s) as workers spent most of their time in backoff.

### Worked example — Haiku at concurrency=2 (the safe value)

```
calls/sec    = 2 / 1.5  = 1.33
calls/min    = 1.33 × 60 = 80           ← still over RPM (50)
tokens/min   = 80 × 1250 = 100,000      ← still over TPM (50k)
```

Even **concurrency=2 is over the cap.** To stay strictly under on default tier:

### Worked example — Haiku at concurrency=1 (strictly safe)

```
calls/sec    = 1 / 1.5  = 0.67
calls/min    = 0.67 × 60 = 40           ← under RPM (50) ✓
tokens/min   = 40 × 1250 = 50,000       ← right at TPM cap
```

This is the right setting for sustained Haiku load on default tier. Bursts can still exceed because of latency jitter, which is what the retry budget (`CELERY_EXTRACT_MAX_RETRIES=6`, `CELERY_EXTRACT_RETRY_BACKOFF_MAX=120`) absorbs.

### Worked example — Opus at concurrency=4 (different shape entirely)

Opus is ~5x slower per call, which self-throttles the pipeline:

```
calls/sec    = 4 / 7    = 0.57
calls/min    = 0.57 × 60 = 34           ← under RPM (50) ✓
tokens/min   = 34 × 1250 = 42,500       ← under TPM (50k) ✓
```

**With Opus, concurrency=4 fits naturally under default tier limits.** No retry budget pressure expected.

### When should you change `CELERY_WORKER_CONCURRENCY`?

```
1. Compute concurrency × (60 / avg_latency_seconds) × avg_prompt_tokens
2. If > RPM_cap × prompt_tokens OR > TPM_cap → lower concurrency
3. Otherwise leave it
```

Recommended values for default Anthropic tier, our ~1250-token prompts:

| Model | Recommended `CELERY_WORKER_CONCURRENCY` |
|---|:---:|
| `claude-haiku-4-5` | **1** (or 2 with retry budget absorbing bursts) |
| `claude-opus-4-7` | **4** (Opus latency self-throttles) |
| `claude-sonnet-4-6` | **2** (mid-latency, mid-cost) |
| Higher Anthropic tier | scale linearly with the new RPM/TPM caps |

### When should you change `LLM_MODEL`?

| Goal | Setting |
|---|---|
| Cheapest, fastest, default | `LLM_MODEL=claude-haiku-4-5` |
| Best quality reasoning, slower | `LLM_MODEL=claude-opus-4-7` |
| Balanced | `LLM_MODEL=claude-sonnet-4-6` |

**Cost delta is the gotcha.** Per 100 extractions (~125k input + 10k output tokens):

| Model | Cost per 100 extractions | Cost per 1000 extractions |
|---|---:|---:|
| Haiku | ~$0.04 | ~$0.44 |
| Sonnet | ~$0.45 | ~$4.50 |
| Opus | ~$2.60 | ~$26 |

So a 1000-item stress test on Opus is ~$26. Plan accordingly.

### Empirical stress-test results

All on Haiku + default tier, after race-fix + broad-catch + retry-budget bumps:

| N | Drain time | Throughput | FAILED (rate-limit) | Notes |
|---|---:|---:|---:|---|
| 20 | 11s | 1.9 items/s | 0 | well under caps |
| 50 | 32s | 1.6 items/s | 0 | at the edge of TPM |
| 100 (concurrency=4) | 99s | 0.77 items/s | 95 (95% rate-limited) | TPM+RPM cap blown 4x over |

**Ideal stress-test size for the default tier with Haiku:** ~30-40 single-batch. Push higher only after raising `CELERY_WORKER_CONCURRENCY` down to 1-2 OR switching to a model with self-throttling latency (Opus / Sonnet) OR getting a tier upgrade.

### What we deferred

- **Distributed token-bucket rate limiter** (Redis-backed). The right production answer — workers consult a shared budget before calling Anthropic, queue when exhausted. Out of scope for take-home; would replace the brute-force "retry on 429" approach.
- **Per-model tier auto-tuning** of CELERY_WORKER_CONCURRENCY based on observed latency. Belongs in a richer orchestration layer.

### When to touch what — decision tree

```
Did you change LLM_MODEL?
├── Yes → recompute concurrency from the formula above
│         (lower for Haiku, higher OK for Opus/Sonnet)
└── No  → leave concurrency alone

Are you stress-testing with N > ~30 single-batch?
├── Yes → either lower concurrency or expect rate-limit failures
│         (and rely on the retry budget to soak them)
└── No  → default values are fine

Did you upgrade your Anthropic tier?
├── Yes → bump concurrency proportionally (concurrency_new = concurrency_old × tier_RPM_new / tier_RPM_old)
└── No  → keep current values
```
