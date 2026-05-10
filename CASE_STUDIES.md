# Case studies

Failures hit during development, their root causes, the fixes, and the engineering lesson each one left behind. Ordered roughly by depth — the meaty distributed-systems ones first, UX defects last.

Every case study follows the same shape:

- **Symptom** — what the operator / user observed
- **Root cause** — the technical explanation
- **Fix** — what we shipped, with commit hash
- **Lesson** — the engineering takeaway

---

## Case study 1 — `asyncio.run()` + module-level engine = "Future attached to a different loop"

### Symptom
Worker tasks for the first burst of Phase-4 testing crashed with:
```
RuntimeError: Task <Task pending coro=<_do_extraction()>> got Future
<Future pending> attached to a different loop
```
3 of 4 stress-test rows orphaned in PROCESSING status.

### Root cause
Celery prefork workers are sync. Our extraction code is async. We bridge with `asyncio.run(...)` per task — which spins up a fresh event loop each invocation and tears it down on return.

SQLAlchemy async engines bind to the loop on first use. Caching the engine at module level tied it to the FIRST loop, then subsequent tasks tried to reuse pool connections that lived on a now-closed loop → the cross-loop Future error.

### Fix (commit `2cbd074`)
Replaced the module-level singleton with a per-task context manager `worker_session_scope` that builds + disposes the engine inside the async body. ~5ms per-task overhead vs ~1s LLM call — negligible.

```python
@asynccontextmanager
async def worker_session_scope() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, ...)
    try:
        async with async_sessionmaker(engine)() as session:
            yield session
    finally:
        await engine.dispose()
```

### Lesson
**`asyncio.run()` rebinds the event loop.** Anything tied to "the loop" via lazy init at module scope — engines, semaphores, queues — must live inside the same `asyncio.run()` block that uses it. A production-scale worker would use `worker_process_init` for a long-lived loop per process; for PoC, per-task setup is simpler and the overhead is invisible.

---

## Case study 2 — Dispatch-before-commit race

### Symptom
20-item stress test → 18 rows orphaned in PROCESSING. Worker logs:
```
ERROR/ForkPoolWorker-1 feedback_not_found_for_extraction
...succeeded in 0.014s: {'feedback_id': 88, 'status': 'not_found'}
```
The worker reported success (with a clean early-return) but the DB row never moved off PROCESSING.

### Root cause
In `FeedbackService.create_feedback`:
```python
feedback = await self.repo.create(...)   # session.add + flush, NOT commit
extract_feedback_task.delay(feedback.id)   # RPUSH to Redis broker
```

The `flush()` made the row visible to **the session's own transaction**, not to other connections. The request-end `session.commit()` (in `db.get_session`) only ran when the route returned. But `task.delay()` is ~1ms; the worker's `SELECT * FROM feedback WHERE id=…` happens within ~5ms; the request commit hasn't fired yet.

Worker queries → row doesn't exist → returns `status="not_found"` → row stays PROCESSING forever.

### Fix (commit `e1b1a48`)
Commit the row BEFORE dispatching:

```python
feedback = await self.repo.create(...)
await self.repo.session.commit()        # ← row visible to workers now
extract_feedback_task.delay(feedback.id)
```

~5-10ms extra per submission. The request-end commit becomes a no-op (no pending changes), which is fine.

### Lesson
**Visibility ≠ persistence ≠ commit.** In multi-process systems, anything you hand to "other code" (broker, queue, IPC) must reference state that's already visible to that other process. `flush()` is local; only `commit()` crosses the connection boundary. Test this with `pg_stat_activity` queries from a second psql session if you're not sure.

---

## Case study 3 — Worker exception not in `except LLMError` orphans the row

### Symptom
4 PROCESSING rows from earlier debug iterations stayed stuck even after their underlying bugs were fixed. The Celery result backend recorded them as FAILURE — but the DB rows never flipped.

### Root cause
`_do_extraction` only caught `LLMError` to flip status to FAILED:

```python
try:
    result, metadata = await extract_insights(text)
except LLMError as error:
    feedback.status = FAILED
    ...
    raise
# any OTHER exception (AttributeError, RuntimeError, ConnectionError,
# KeyError, OOM, ...) propagates out → row stays PROCESSING forever
```

Two distinct bugs (Case Studies 1 and 4) had been hitting the path BEFORE `extract_insights` even got called, leaving the row untouched.

### Fix (commit `a5e48db`)
Factor the fail-and-notify path into `_mark_failed()` and add a broad `except Exception` branch:

```python
try:
    result, metadata = await extract_insights(text)
except LLMError as error:
    await _mark_failed(session, ..., context="celery_task_llm_error")
    raise  # autoretry per Celery decorator
except Exception as error:  # noqa: BLE001 — last-line defense
    await _mark_failed(session, ..., context="celery_task_uncaught")
    raise  # no autoretry — these are our bugs, retrying won't help
```

The bare `Exception` is NOT in `autoretry_for`, so Celery treats it as permanent FAILURE without burning retry budget on logic bugs.

### Lesson
**`except SpecificError` is for behavior, not safety.** Use it when you want different recovery for different exceptions. Pair it with a `except Exception` at the boundary to guarantee invariants (row state in our case) hold regardless of what falls through. Re-raise to preserve the original traceback; just update mutable state on the way out.

---

## Case study 4 — `APIConnectionError` doesn't have `status_code`

### Symptom
Worker crashed during stress testing:
```
AttributeError: 'APIConnectionError' object has no attribute 'status_code'
File "/app/app/llm/client.py", line 81, in call_with_retry
  if e.status_code and 500 <= e.status_code < 600:
```

Surfaced more often in worker context than backend (transient connection issues are statistically more common across worker processes).

### Root cause
Anthropic SDK exception hierarchy:
- `APIError` — base
- `APIStatusError` — extends APIError, **has** `status_code`
- `RateLimitError` — extends APIStatusError
- `APIConnectionError` — extends APIError, **no** `status_code` (never got a response)
- `APITimeoutError` — extends APIConnectionError

Our handler caught `APIError as e` then unconditionally accessed `e.status_code`. For `APIConnectionError`, that attribute doesn't exist.

### Fix (commit `80247ae`)
`getattr` with sentinel, treat unknown status as transient:

```python
except APIError as e:
    status_code = getattr(e, "status_code", None)
    is_transient = status_code is None or (500 <= status_code < 600)
    if is_transient:
        # backoff + retry
    else:
        raise LLMError(str(e)) from e
```

A None status_code means "no response" — exactly when we want to retry, so the new branch lumps it with 5xx.

### Lesson
**Don't access attributes that aren't on the base type you caught.** Either narrow the except (catch only `APIStatusError` if you need `status_code`), use `getattr` with a default, or check `isinstance` first. SDK exception hierarchies are inheritance trees and the leaves carry different attribute surfaces.

---

## Case study 5 — Redis connection pool exhaustion under SSE + stress load

### Symptom
During a 100-item stress test with 2 dashboard tabs open:
```
GET /v1/summary → 500 Internal Server Error
GET /v1/events  → 500 (SSE subscribe failed)
GET /v1/stats   → 500 intermittently

redis.exceptions.MaxConnectionsError: Too many connections
```

From the user's view: the dashboard "froze" at a stale total count even as feedback kept being submitted. Total wasn't incrementing because `/v1/stats` was 500-ing on every poll.

### Root cause
Backend's async Redis client was sized at `max_connections=10`:
```python
_redis_client = redis_async.from_url(
    settings.redis_url,
    max_connections=10,
)
```

Each connected dashboard tab opens an SSE stream and holds 1-2 long-lived pubsub connections. The `/v1/summary` cache-read path needs a connection per request. The `/v1/stats` polling pattern (every 5s) needs another. With 2 tabs:

- 2 × SSE pubsub = ~3 connections held
- Concurrent `/v1/stats` polls (race during a stress) = ~5+ connections
- `/v1/summary` cache hit on every page load = +1
- Worker pub/sub publishes (separate sync client, no pool issue) = isolated

Easy to exceed 10. When the pool is empty, `pop from empty list` → `MaxConnectionsError`.

### Fix (commit `ff2d09a`)
Bumped to 50 and made it a Settings field:
```python
redis_max_connections: int = Field(default=50, ge=5, le=500)
redis_socket_connect_timeout_seconds: float = Field(default=5.0, gt=0.0)
```

Plus added connect timeout — without it the pool blocks indefinitely on a degraded Redis.

### Lesson
**Long-lived connections (SSE pubsub, websockets) need pool sizing that accounts for them separately.** A pool of 10 is fine for "10 concurrent short-lived requests" but pathological when each tab pins 1-2 slots for the duration of the browser session. Rule of thumb: `tabs × persistent_connections + max_concurrent_requests + safety_margin`. We sized for ~10 tabs at 50 connections; production would either bump it further or split the persistent and request pools.

---

## Case study 6 — Anthropic rate limits vs worker concurrency

### Symptom
100-item stress test on Haiku, default Anthropic tier:
- 76 extracted, **24 FAILED with `LLMRateLimitError`**
- Drain time 99s (vs the ~37s the math said)
- Throughput dropped from 1.87 items/s (at N=20) to 0.77 items/s (at N=100)
- p95 latency climbed 2.3s → 3.7s → 6.6s as the test ran (backpressure-induced)

A second 100-item run with the bumped retry budget (6 attempts, 120s backoff cap) made it worse: **95 of 100 failed** with rate-limit errors. The retries were just being throttled too.

### Root cause
Anthropic enforces TWO rate limits per org per model, default tier:

| Cap | Value | Per |
|---|---|---|
| RPM | 50 | requests/min |
| TPM | 50,000 | input tokens/min |

A 429 fires the moment either is exceeded. With ~1250 input tokens per call (system prompt + tools schema + feedback text), **TPM is the binding constraint**:

```
50 RPM × 1250 tokens = 62,500 tokens/min   ← 1.25× over TPM cap
```

Our worker at `CELERY_WORKER_CONCURRENCY=4` with Haiku's ~1.5s avg latency:
```
calls/sec  = 4 / 1.5  = 2.67
calls/min  = 160          ← 3.2× over RPM
tokens/min = 200,000      ← 4× over TPM
```

The retry budget was just absorbing the burn rate, not preventing it.

### Fix (commits `e17dedd`, `bc2f6c2`, `ff2d09a`)
1. Documented the formula in this case study + recommended values per model (see "When to change CELERY_WORKER_CONCURRENCY" below).
2. Bumped Celery retry budget defaults so transient spikes get absorbed instead of failing fast.
3. Added the dashboard "Stress test (100)" button + `/v1/feedback/stress-test` endpoint capped at 200 — so accidental load tests can't burn budget.

**Did NOT add a distributed token-bucket** — the right production answer (Redis-backed budget, workers consult before dispatching to Anthropic) but out of scope. Documented in the "Deferred" section below.

### Lesson
**Read the rate-limit docs before tuning concurrency.** The formula `concurrency × (60 / avg_latency) × prompt_tokens` vs your tier's caps is non-negotiable arithmetic. If you exceed it, retries don't help — they just spread the failures over a longer window.

For our defaults:

| Model | Recommended `CELERY_WORKER_CONCURRENCY` (default Anthropic tier) |
|---|:---:|
| `claude-haiku-4-5` | 1 (TPM-bound; bursts absorbed by retry) |
| `claude-sonnet-4-6` | 1-2 (untested empirically; estimate from latency) |
| `claude-opus-4-7` | **1** (empirical; see update below) |

### Empirical update — Opus latency assumption was wrong

The original recommendation said "Opus = concurrency 4, slow latency self-throttles". A 500-item Opus stress test (aborted at item 28 for budget reasons but still informative) found:

| Variable | Original assumption | Empirical measurement |
|---|---:|---:|
| Opus avg latency on this prompt | 5-10s ("slow") | **3.4s** (faster than expected) |
| Prompt size | ~1250 tokens | **~1730 tokens** (system prompt + tools schema is larger than eyeballed) |
| Calls/min at concurrency=3 | 26 (under 50 RPM cap) | **55** (1.1× over) |
| TPM at concurrency=3 | 32k (under 50k cap) | **96k** (1.9× over) |

Why no 429s observed in the 30s window: Anthropic's rate limit is a 60-second sliding window. The burn rate was 1.9× the cap but the test didn't run long enough for the window to accumulate. A sustained 500-item drain would have started failing within the first 30-60s.

**Revised Opus math:** at avg latency 3.4s with our ~1730-token prompts:

| Concurrency | calls/min | TPM input | Within caps? |
|---|---:|---:|---|
| 1 | 17.6 | 30.5k | yes (comfortable) |
| 2 | 35.3 | 61k | RPM yes, **TPM no** |
| 3 | 52.9 | 92k | **both over** |
| 4 | 70.6 | 122k | **way over** |

**Updated recommendation: `CELERY_WORKER_CONCURRENCY=1` for Opus on default tier.** The "slow Opus self-throttles" framing only holds if average latency stays above ~5s; for our prompt size Opus is closer to 3.4s and the math flips. To drain a large Opus batch cleanly, either drop concurrency to 1 (predictable, ~17 calls/min), upgrade the Anthropic tier, or implement a Redis-backed token-bucket throttle (deferred work).

### Updated cost table (with the real prompt size)

Per call: ~1730 input + ~140 output tokens (was eyeballed at 1250+100).

| Model | $/call | 100 items | 500 items |
|---|---:|---:|---:|
| `claude-haiku-4-5` | ~$0.00061 | $0.06 | $0.31 |
| `claude-sonnet-4-6` | ~$0.0066 | $0.66 | $3.30 |
| `claude-opus-4-7` | ~$0.036 | $3.60 | **$18** |

The 500-item Opus run was budgeted at ~$13 based on the original 1250-token estimate; the actual cost at 1730 tokens would've been ~$18. The test was aborted at ~$1.05 spent (28 calls completed), which validates "the bigger prompt makes everything 40% more expensive than the back-of-envelope predicted."

---

## Case study 7 — Anthropic client cached on stale event loop (asyncio.run revisited)

### Symptom
Worker logs showed a `llm_transient_retry` WARNING immediately after every `extract_feedback_task_started` event — even though every task ultimately completed with HTTP 200 OK and `status=extracted`:

```
[ForkPoolWorker-3] extract_feedback_task_started
[ForkPoolWorker-3] llm_transient_retry            ← 13ms later
[ForkPoolWorker-3] HTTP Request: POST … 200 OK   ← 3.4s later
[ForkPoolWorker-3] succeeded                     ← clean extraction
```

The warning is harmless (we recover), but **every task burned ~1s of unnecessary backoff** between the first failed attempt and the retry. On a 100-item drain that's ~100s of wasted wall-clock time. Empirically we measured 3.4s avg latency on Opus when actual extraction was ~2.4s — the extra 1s was this bug.

### Root cause
**Same pattern as Case Study 1.** `client.py` lazy-inits a module-level `AsyncAnthropic` client. The client wraps an `httpx.AsyncClient` whose connection pool binds to the loop it was created in.

Celery worker tasks bridge sync → async via `asyncio.run()`, which creates a fresh event loop per task. The first task in a fork creates the client + pool bound to **that task's loop**. When the task ends, `asyncio.run()` closes the loop. The next task gets a **new** loop but reuses the same module-level client — whose pool is now orphaned on a dead loop.

First call attempt on that next task: connection-level failure (the pool can't operate on a dead loop) → raised as a connection-class `APIError` → caught by the broad-transient branch in `call_with_retry` → log warning + backoff 1s + retry. The retry creates fresh connection state on the live loop, succeeds.

We fixed this exact pattern for the SQLAlchemy engine in Case Study 1 via `worker_session_scope`. We missed it for the Anthropic client.

### Fix (initial: commit `d49dbe2`; correction: commit `<this commit>`)
Loop-aware client cache. Rebuild the client when the current loop differs from the loop that created the cached one.

**Initial fix (`d49dbe2`) tracked the loop via `id()` — DID NOT WORK.** A 30-item Haiku stress test post-fix still showed 29/30 tasks emitting the warning. Diagnosis: `id()` returns a memory-address int that CPython **reuses** when the previous object is GC'd. `asyncio.run()` closes the loop after each task, the loop gets GC'd, and the next `asyncio.run()` very often gets a new loop at the same address → same `id()` → check missed every rebuild.

**Correct fix:** compare loop OBJECTS via `is`/`is not`. Python's object identity is preserved across the object's lifetime and isn't fooled by address reuse.

```python
_client: AsyncAnthropic | None = None
_client_loop: asyncio.AbstractEventLoop | None = None

def get_client() -> AsyncAnthropic:
    global _client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _client is None or _client_loop is not current_loop:
        settings = get_settings()
        _client = AsyncAnthropic(api_key=..., timeout=..., max_retries=0)
        _client_loop = current_loop   # replace ref, no accumulation
    return _client
```

Rebuild is cheap (no DNS/TLS until first call). We hold at most one loop reference at a time (the assignment drops the previous ref → it GCs naturally when its task ends). On the FastAPI side, the single long-lived loop means the check is a no-op (current_loop stays the same) and the client is reused as before.

### Lesson
**`asyncio.run()` in Celery means every "module-level lazy-init that touches the loop" is a bug waiting to happen.** Audit list when bridging sync ⇄ async per task:
- SQLAlchemy async engine (fixed in Case Study 1)
- Anthropic / httpx client (this case study)
- `asyncio.Semaphore` — safe ONLY if never contended (lazy-binds on first await; ours has 5 slots and 1 caller, so it never binds)
- `asyncio.Queue`, `asyncio.Event`, any other primitive that lazy-binds to a loop

The general fix is one of:
1. **Per-loop cache** (this case study's approach) — track loop id, rebuild on change.
2. **Per-call construction** — build the resource inside the async body, dispose after (Case Study 1's approach).
3. **One long-lived loop per worker** via `worker_process_init` — Celery signal, single loop survives all tasks in a fork. Production-scale answer; out of scope for PoC.

The PoC uses (1) for the LLM client and (2) for the DB engine. Both eliminate the cross-loop issue without restructuring the worker bootstrap.

### How we found it
The bug shipped with Phase 4. We noticed it during a 500-item Opus stress test when a sub-agent's report flagged "`llm_transient_retry` WARNING emitted after every `extract_feedback_task_started`". The agent thought it was a log-ordering artifact; debugging showed it was the real bug above.

A canary: any retry warning that fires "on every task, then succeeds 1-2s later" is this pattern, regardless of which underlying resource is loop-bound. Look for module-level globals that touch the loop.

### Sub-lesson: don't use `id()` for "is this the same object as before?" across lifetimes
The first patch attempt compared `id(loop)`, which seemed cleaner than holding the loop object itself. **It didn't work** — `id()` in CPython is the memory address, which gets reused after GC. A 30-item Haiku regression test caught it (29/30 tasks still emitted the warning despite the "fix"). Use `is`/`is not` for object identity that needs to survive intervening GCs.

---

## Minor issues — also fixed, smaller engineering surface

### Multi-paste defaulted to "Single" mode
**Symptom:** pasting two paragraphs into the form created one feedback row containing both paragraphs, instead of two separate rows.

**Cause:** `PasteForm` defaulted to single-mode. The splitter regex was fine — it just never ran.

**Fix (`3d54b95`):** changed default to "Multiple feedback items". Single-mode users with one item still work cleanly (splitter returns one element).

**Lesson:** defaults should match the realistic primary use case. This app is for batch processing feedback — multi-paste is the common path, single is the special case.

### "This week" KPI equaled "Total feedback" on short-lived demos
**Symptom:** dashboard showed `Total feedback: 1213` and `This week: 1213` — the two tiles displayed identical numbers, looking like a bug. Also: total wasn't changing during a stress test drain even though the "processing" pill was ticking down, which read as "the dashboard is stuck".

**Cause:** two converging issues — (1) `weekly_delta.this_week_count` measures rows created in the last 7 days; on a 14-hour-old dataset, every row qualifies → this_week == total. (2) `total_feedback` counts rows at INSERT time (status=PROCESSING included), not at extraction time — so during a stress test it jumps at dispatch and stays flat during the drain. Two correct numbers reading as broken because the labels didn't match what the user expected to see move.

**Fix (`<this commit>`):** swap the rolling window from 7 days to 24 hours. Renamed: `WeeklyDelta` → `TodayDelta`, `weekly_delta` → `today_delta`, "This week" → "Today", `weekOverWeek` → `dayOverDay`. Also widened the Total-feedback hint from `9 skipped, 597 failed` to `707 extracted, 9 skipped, 597 failed` so the live-growing `extracted` count is visible during a drain (it's now the leftmost number in the hint, so users see it move as workers complete tasks).

The 24h window also matches the AI summary widget's `summary_lookback_hours=24` — same cohort across both widgets eliminates the "summary says 26% but tile says 36%" class of confusion from Case Study minor-issues.

**Lesson:** when two numbers should look different but happen to coincide on demo-scale data, users read it as a bug regardless of the math. Pick window sizes that produce visibly different values in normal use, and put the most-frequently-changing sub-count in the hint so the tile *moves* even when the headline number doesn't.

### Summary widget showed different percentages than KPI tiles
**Symptom:** KPI tile says "36% Positive / 50% Negative". Summary widget below says "Sentiment skews negative (58% negative vs 26% positive)". User reasonably asked "why don't these match?"

**Cause:** they measure different cohorts. KPIs compute `count / total_extracted` over all-time extracted feedback. Summary's LLM computes its own % over the 50 items it saw in the prompt (last 24h, capped).

**Fix (`ecfd4b4`):** tightened the summary prompt to use qualitative language ("skews negative") instead of specific percentages. Specific mention-counts ("8 mentions of mobile login") still allowed because they're triage-useful and don't conflict with the KPIs.

**Lesson:** if two UI elements show numbers that look directly comparable but compute over different data, users will read them as inconsistent. Either align cohorts or remove the conflicting numbers.

---

## Deferred (graduation work)

- **Distributed token-bucket rate limiter** — Redis-backed, workers consult shared budget before dispatching to Anthropic. The right production answer to Case Study 6.
- **Stuck-row reaper Beat task** — periodic scan for PROCESSING rows older than `extract_timeout + safety_margin`. Belt-and-suspenders for cases the broad-catch in Case Study 3 can't help (worker SIGKILL, broker outage during dispatch).
- **Separate Redis pool for SSE pubsub** — currently shares the request pool. At higher concurrency, splitting them prevents long-lived connections from starving short-lived ones (or vice versa).
- **Alembic migrations** — currently relies on `Base.metadata.create_all()` which only handles missing tables. Schema changes require a volume wipe today.
