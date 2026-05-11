# Notes for reviewers

## Context-engineering decisions I'm proudest of

**1. Scoped memory + on-demand skills, not one giant CLAUDE.md.** The root
CLAUDE.md points at scoped files rather than dumping. Real conventions
live in `backend/CLAUDE.md` and `frontend/CLAUDE.md`, which auto-load
only when Claude reads files in that directory. The `prompt-engineering`
skill carries the deep iteration workflow and loads on invoke, not per
turn. `@.claude/context/architecture.md` is imported into the root for
shared system shape. I deleted two intermediate skills mid-project
(`backend-patterns` early, then `llm-workflow` late) once their content
drifted toward generic patterns or duplicated `backend/CLAUDE.md` —
a skill only earns its slot when the content is genuinely
project-specific AND not derivable from the auto-loaded CLAUDE.md.

**2. A full prompt-iteration pipeline: generator → evaluator → human →
golden set.** Two narrow sub-agents form the loop. `edge-case-generator`
proposes JSONL candidates for gaps; `prompt-evaluator` runs the eval,
writes a timestamped JSON report to `evals/reports/`, reports pass/fail
vs `baseline.json`. The loop ran seven rounds total. Rounds 1-3 took
20 → 40 goldens (v1.3 → v1.4) and surfaced an over-extraction weakness
that v1.4 fixed with a "one-topic discipline" rule (`overall_pass_rate`
80% → 95%). Rounds 4-5 added 14 more candidates: round 5 surfaced three
more failure modes (action-items suppressed by positive sentiment,
dev-API vocab missing from the synonym list, "works as expected"
misread as positive) that v1.5 hardened — 39 → 53 goldens, all metrics
back to 100%. Round 6 tried to handle absurd inputs ("product worked
1000 yrs ago and now is bad") two wrong ways before round 7 landed it
right: first a brittle regex validator (rejected — only catches
patterns I anticipated), then a v1.6 "distill into generic action item"
rule (rejected — quietly inflated the dashboard's negative count).
v1.7's fix is the structurally interesting one: a new `is_noise` field
on the `ExtractionResult` schema. The model gets an explicit channel to
say "this is noise, skip it"; the worker maps `is_noise=true` to
`status=skipped, skip_reason=noise` (mirrors the existing
`language!='en'` skip path). The lesson reinforced: when the LLM keeps
producing technically-correct-but-unwanted output, the answer is often
to give it a new output channel rather than adding more prompt rules.
Each piece — agents, harness, baseline gate, schema field, worker
branch — has thresholds, file paths, and decision criteria baked in
rather than punted to the model.

**3. `CASE_STUDIES.md` as a separate decision log.** Production-shaped
incidents (Anthropic rate-limit ceiling, asyncio event-loop binding bug,
dispatch-before-commit race) live in a dedicated log. CLAUDE.md gotcha
sections cross-reference it. Keeps CLAUDE.md tight without losing the
"why" behind surprising design choices.

## What didn't work, and what I changed

**The Case Study 7 fix that wasn't a fix.** First attempt cached the
Anthropic client keyed by `id(asyncio.get_running_loop())` — passed my
manual smoke test, looked right on paper. A 30-item Haiku stress test
(via `backend/scripts/stress_test.sh`) caught it: 29 of 30 tasks still
emitted `llm_transient_retry`. CPython recycles memory addresses when
objects are GC'd; `asyncio.run()` per Celery task creates+closes+GCs a
loop each time, so the new loop kept getting the same `id()` and the
cache miss never fired. Switched to object identity (`is`/`is not`) and
the warning rate went to zero. Lesson, encoded in `client.py:get_client()`
as a comment: declaring a fix needs evidence, not just "looks right."

**The 429 retry-knob rabbit hole (Case Study 8).** A 100-item Haiku burst
left 24 tasks in `FAILED` with `LLMRateLimitError`. First reaction was
"retries are broken, tune them harder." Three knob-tweaks later the
failure count was 5 instead of 24 and I was still tuning. The real fix
was a one-line config change: `CELERY_WORKER_CONCURRENCY=3 → 1`. The
math from Case Study 6 was already there — `3 workers × ~2s latency ×
~1.5k tokens ≈ 90k tokens/min vs the 50k TPM cap, 1.8× over.` No retry
config beats that. Retries spread failures over time; they don't change
the average burn rate. The retry-after header honor + jitter floor +
budget bump are still worth keeping (cleaner backoff, no thundering-herd
re-fire on full-jitter zero), they just weren't load-bearing for the
failure problem. Lesson: when iterating retry settings shrinks the
failure count monotonically but never to zero, **stop tuning** and
recompute the upstream rate against the cap. That's the only number
that matters.

## What I'd add if this were long-lived

- A golden set for the summary prompt (currently only extraction has one).
- An automated "generate → eval → diff → file PR" cron loop on top of
  the existing two-agent pipeline.
- A drift-checker that diffs CLAUDE.md claims (API paths, folder layout,
  Settings field names) against the actual code.
- Real CI spend monitoring on the eval workflow.
- **Redis-backed token-bucket throttle** so workers consult a shared budget
  before dispatching to Anthropic. CS6/CS8 deferred this; the current
  answer is "set concurrency to 1." A token bucket lets concurrency scale
  back up without re-hitting the TPM cap, and trivially survives tier
  upgrades (just bump the bucket size).
- **Process-wide event loop per Celery worker** (`worker_process_init`
  signal). Kills the `Event loop is closed` cosmetic noise from CS8's
  sub-issue, drops the ~1s wasted backoff per task documented in CS7,
  and lets the httpx connection pool actually pool across calls.
- **Streaming summary** — SSE token-stream from Anthropic to the
  `SummaryWidget` so prose appears as the LLM writes it. The SSE
  infrastructure is already there; this is a wiring change in
  `summarize.py` + the widget.
- **Persist every regenerated summary blob** keyed by cohort fingerprint
  in a `summary_history` table. Free audit trail of how prose evolves
  as the dataset grows; pairs naturally with the fingerprint-skip work.
- **Alembic migrations** replacing the `Base.metadata.create_all()`
  bootstrap. Today, any column-type change requires `docker compose
  down -v` to drop the postgres volume. Production graduation work.
- **Per-row cost meter** on `/feedback` and the summary widget — surface
  `input_tokens × price + output_tokens × price` per row + per summary
  regen, so concurrency/retry trade-off conversations stay quantified
  instead of intuited.

**On hooks/slash commands:** I didn't write any. The take-home scope had
no recurring event-driven trigger that warranted a hook, and no
muscle-memory shortcut that warranted a slash command. Per the PDF's
"call it out rather than reach for them for show" — calling it out.
