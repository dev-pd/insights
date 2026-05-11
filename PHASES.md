# PHASES.md

How this project was built. Phased delivery, key decisions, and tradeoffs.

This document focuses on **engineering process** rather than feature lists. The README covers what the project does. The NOTES cover architectural decisions and known limitations. This doc covers **how the build evolved over time** - which decisions were made when, which gaps were caught and corrected, and what the rationale was at each stage.

---

## Summary

The project was delivered in five major phases broken into sub-phases for shippability. Each sub-phase landed as a focused git changeset that left the application in a working state. This kept the build verifiable at every step and made the git history reviewable.

| Phase | Theme | Scope |
|---|---|---|
| **1** | Foundation | Docker setup, FastAPI skeleton, Postgres, Redis, nginx, health checks |
| **2** | Synchronous extraction | LLM call path, validation, persistence, paste form, feedback list |
| **3** | Stats dashboard | KPIs, charts, themes, sentiment trend |
| **3.1** | Restructure | Three URL routes, navbar, separation of concerns |
| **3.2** | Feedback table | Table layout, expandable rows, filter, pagination |
| **3.2.1** | Multi-paste + layout | Single/Multiple modes, blank-line splitting, batch endpoint, layout consistency |
| **3.2.2** | Search | Full-text search across feedback/themes/actions, debounced input |
| **3.3** | Dashboard upgrade | 6 KPIs with weekly delta, 7-day theme window |
| **3.4** | AI summary | LLM-generated dashboard summary with Redis cache and manual refresh |
| **3.4.1** | Cost tracking | `llm_usage` audit table for unified cost across all LLM call sites |
| **4** | Async processing | Celery worker pool, Redis pub/sub, SSE for real-time updates, Beat for cache warming |
| **5** | Polish | Eval harness, prompt iteration, baseline gating, CI workflow, documentation |

The sub-phase numbering reflects the natural seams in the work: a `.1` was a fix-up or focused addition after the parent phase had shipped, not a planning artifact.

---

## Phase-by-phase narrative

### Phase 1: Foundation

Established the basic stack: FastAPI backend, Postgres for persistence, Redis for cache, nginx as reverse proxy, Next.js frontend, all in docker-compose. Health check endpoints for each service. The goal was a verifiable "hello world" across the full stack before any feature work.

This phase produced no user-visible features. It produced **infrastructure that subsequent phases could build on without rework**. The decision to invest in Docker orchestration up front paid off repeatedly - every later phase that added a new service (worker, beat) slotted in cleanly because the foundation was sound.

### Phase 2: Synchronous LLM extraction

Implemented the core extraction flow: paste feedback → validate → call Anthropic → parse tool_use response → persist row → return to user.

Key decisions:

- **Tool use over text parsing.** Anthropic's tool use feature returns structured JSON that maps to a Pydantic schema. No regex parsing, no JSON-in-text fragility.
- **Pre-LLM validation.** Empty strings, too-short text, and clear gibberish are caught before the LLM call. Saves cost and surfaces specific skip reasons to the user.
- **Status enum on the feedback row.** `EXTRACTED`, `SKIPPED`, `FAILED` from day one - even though `PROCESSING` wasn't needed yet, the enum was sized for future async work.
- **`llm_metadata` JSONB field on Feedback.** Captured tokens, latency, prompt version, model. Later migrated to dedicated audit table in 3.4.1, but the per-row capture worked for the synchronous era.

What this phase did NOT do, deliberately:

- No retry logic in the application layer (the SDK handles retries adequately for sync flow)
- No batching - one feedback per request
- No streaming - synchronous request-response

These limitations would be revisited in 3.2.1 (batch) and Phase 4 (async).

### Phase 3 (original): Stats dashboard

Built the first version of the dashboard: 4 KPI tiles, top themes bar chart, sentiment trend over time. SWR for client-side data fetching with auto-refresh.

The chart implementation went through three iterations during this phase before settling on the final approach. Each iteration revealed a real concern (label visibility when scrolling, arbitrary cardinality of themes, axis stability), and the final version is documented separately. This was the first time in the build where **the right answer required iterating, not planning ahead**.

### Phase 3.1: Restructure to three routes

A re-reading of the take-home requirements revealed that the single-page layout (form + list + dashboard stacked) wasn't matching what users actually needed. Submitted feedback isn't dashboard data - it's an input action. Browsing past feedback isn't dashboard data either - it's a separate analyst task.

Restructured into three routes:
- `/` - Dashboard (executive view only)
- `/add` - Add Feedback (paste form, isolated)
- `/feedback` - Feedback list (browse, search, filter)

This decision drove the architecture for every subsequent phase. The clean separation meant later additions (multi-paste, search, AI summary) had obvious homes.

A common navbar component became the shared element across all three routes, with active-route highlighting.

### Phase 3.2: Feedback table with filter and pagination

The Phase 2 feedback list was a vertical stack of cards. For an analyst workflow, that doesn't scale - scanning 50 cards is much harder than scanning a 50-row table. Replaced with:

- Table layout (time, sentiment, themes preview, full-text preview)
- Click-to-expand rows for full details
- Sentiment filter dropdown
- Page-number pagination (not just prev/next)
- Backend `/paginated` endpoint with offset/limit/sentiment filter

The expand-inline pattern was chosen over a modal because **the analyst keeps their filter context when expanding** - they don't lose place when reading detail. This is the kind of UX detail that comes from thinking about who actually uses the screen.

### Phase 3.2.1: Multi-paste and layout consistency

Two distinct concerns landed in this phase: multi-paste support, and a layout audit.

**Multi-paste:** A re-read of the spec ("paste customer feedback - either one entry at a time, or a batch") revealed that the Phase 2 paste form assumed one feedback per submission. Added a Single/Multiple mode toggle. Multiple mode splits input on blank lines (falls back to single newlines). A "N feedback items detected" badge gives confidence about the split before submission. Max batch size of 50 enforced.

**Layout consistency:** While auditing the new `/add` page, noticed inconsistent container widths across routes - some `max-w-3xl`, some `max-w-5xl`. Standardized to `max-w-5xl` across all three routes plus navbar. Fixed a "Recent feedbacks" typo (it had crept into one component despite the locale being correct).

This phase also introduced the toast notification system - module-level singleton state with a `useToast` hook and `ToastStack` component mounted at root. Toasts are global-by-nature so this avoids React Context boilerplate.

Backend added `POST /v1/feedback/batch` accepting `{texts: string[]}` (1-50). Sequential processing on the backend, not parallel - parallel asyncio.gather would hit Anthropic rate limits and create DB session contention. Sequential is predictable and simple.

### Phase 3.2.2: Search

Another re-read of the spec ("searchable list of feedback") caught that the table only had a sentiment filter - no free-text search. Added a search box on `/feedback` with 300ms debounce. Backend search uses Postgres ILIKE on the text field plus JSONB-cast ILIKE on themes and action_items arrays.

The ILIKE approach was deliberate over full-text search (tsvector + GIN index) because the take-home data scale is in the hundreds. Full-text search would be over-engineering for unmet scale, and is documented in NOTES as graduation work.

### Phase 3.3: Dashboard upgrade

Replaced the original 4 KPIs with 6 smaller tiles:
- Total feedback (with hint showing skipped/failed)
- Positive % (with raw count)
- Negative % (with raw count)
- "This week" or "Today" (with WoW or DoD trend arrow)
- Avg latency
- Total tokens

The trend indicator (↑↓→) appears on the time-bucketed KPI when the delta exceeds ±5%. Below that, the indicator shows "flat" to avoid surfacing noise.

Top themes filter changed from all-time to last 7 days - shows what's currently being discussed rather than what's stable over months. The chart still captures all themes from the data; the 7-day filter is a display choice.

### Phase 3.4: AI summary widget

Added an LLM-generated summary at the top of the dashboard, between KPIs and charts. Anthropic Haiku reads the last 24 hours of extracted feedback and writes 2-3 sentences identifying overall sentiment direction, recurring themes, and any urgent issues.

**Cache strategy:** Single Redis key (`summary:current`) with 1-hour TTL. Get endpoint returns cached if available, generates fresh on miss. Refresh endpoint forces regeneration.

**Initial decision (revised in Phase 4):** No background cron at this stage. Cache warms on next access after expiry. The user has a manual refresh button if they want immediate freshness.

This phase intentionally reused the same Anthropic client, retry logic, and prompt versioning infrastructure from Phase 2 extraction. Different prompt, same plumbing - demonstrates that the LLM infrastructure was built reusably.

### Phase 3.4.1: Unified LLM cost tracking

After Phase 3.4 shipped, the dashboard "Total tokens" KPI revealed a gap: it summed from `Feedback.llm_metadata`, so it only reflected extraction costs. Manual summary refreshes (which also cost tokens) were invisible.

Three options were considered:
- A. `llm_usage` audit table - one row per LLM call
- B. Redis INCRBY counters
- C. Add a separate "Summary tokens" KPI tile

Option A was chosen because Phase 4 was about to add more LLM call sites (async extraction, Beat-scheduled summary regen), and an audit table provides one canonical place for all current and future call types to instrument. This is the same pattern production observability tools use.

The migration:
- New `llm_usage` table: call_type, model, input/output tokens, latency, prompt_version, optional feedback FK
- New `LlmUsageRepository` with `record()` and aggregation methods
- Instrumented both extraction and summary services to record usage
- `StatsService` reads totals from `LlmUsageRepository` instead of summing JSONB on Feedback

The old `Feedback.llm_metadata` field stays for compatibility but is no longer the source of truth for cost.

### Phase 4: Async processing

The largest single phase, and the one with the highest risk. Converted synchronous LLM extraction to background processing with real-time UI updates.

Architecture:
- **POST returns immediately** with `status=PROCESSING` row
- **Celery worker pool** (4 concurrent) processes tasks from Redis queue
- **Redis pub/sub** for event distribution (separate from cache and Celery's own broker/backend, just different logical databases)
- **SSE endpoint** (`/v1/events`) streams events to connected browsers with 30s heartbeats
- **Frontend `useFeedbackStream` hook** uses EventSource, patches SWR cache on per-feedback events, invalidates stats on aggregate events
- **Celery Beat** regenerates the AI summary hourly to keep the cache warm

Failure handling: tasks autoretry on `LLMError`, `TimeoutError`, `ConnectionError` with exponential backoff (capped at 60s) and jitter, max 3 retries. After max retries, the row goes to `FAILED` status with the error captured in metadata.

The decision to include Celery Beat in this phase (rather than skip it as initially planned) came down to marginal cost: Celery infrastructure was already being introduced for async extraction, and Beat is ~30 lines of additional configuration. The benefit - dashboard never has cold-cache slow loads - justified the addition.

**Bugs caught and fixed during this phase:**

- **`uv` not on PATH in container.** The multi-stage Dockerfile drops the uv binary before runtime. Worker/beat commands corrected to invoke celery directly.
- **Beat schedule write permission.** Non-root user can't write to WORKDIR; redirected schedule file to `/tmp`.
- **`asyncio.run() + module-level engine = event-loop binding error.`** Workers spawn fresh event loops via asyncio.run(), but a module-level SQLAlchemy engine binds to the first loop and fails on subsequent calls. Refactored to a per-task `worker_session_scope` context manager that builds and disposes the engine inside the async body.
- **`call_with_retry` AttributeError on APIConnectionError.** Pre-Phase-4 latent bug surfaced because workers see more transient errors than the synchronous backend did. Switched to `getattr(e, "status_code", None)` with None → transient semantics.
- **Pending count drift.** Stale `PROCESSING` rows from pre-fix-3 debug runs accumulated in the database. Documented as known state quirk.

This phase introduced a "Phase 4 gotchas" section in the root CLAUDE.md to capture these for future reference.

**UI changes for async:**

The dashboard header gained a processing pill - a slate-colored badge with a pulsing dot indicator that shows `N processing` when items are pending. The pill hides when the count is zero, so a quiet dashboard stays visually clean.

The page-level heading pattern was also rationalized here. Initially, `StatsDashboard` rendered its own `<h2 text-lg>` heading while `/add` and `/feedback` had `<h1 text-2xl font-bold>` at the page level. The dashboard heading looked smaller than the others. Moved the heading to the page level (matching the other two routes) and removed it from inside the component. The processing pill sits in the same row as the heading.

### Phase 5: Polish

The submission-readiness phase. Initially planned as three sub-phases (tests, evals, docs), reorganized to skip unit tests in favor of a robust eval harness. Justification: this submission is for an LLM eval company - measuring real LLM output quality is a stronger signal than testing pure validation functions. Unit tests stay as graduation work documented in NOTES.

**Eval harness:**

- 20 hand-curated golden cases covering positive/negative/neutral, multilingual, edge cases (sarcasm-adjacent, mixed-with-blocker), and adversarial framings (absurd-historic-frame, feature-request-enthusiastic)
- Some cases explicitly anchor known v1.1 behaviors that should not regress
- Some cases include `expected_action_items_forbidden_substrings` to catch hallucination patterns (e.g., the absurd-historic-frame case ensures the model doesn't parrot "1000 years ago" into action items)
- Metrics: sentiment accuracy (exact match), theme F1 (strict and fuzzy), action item recall, schema validation, cost, latency
- `baseline.json` captures the current quality bar; `--check` mode gates regressions in CI

**Prompt iteration:**

The eval harness immediately revealed two regressions in v1.1: feature requests with enthusiastic language were classified as positive (they should be neutral - the user is asking for a change, not praising what exists), and resolved past-tense complaints were classified as negative (they should reflect resolution dominance).

Prompt v1.2 tightened the sentiment rules and added grounding constraints for action items. Eval scores improved on the regression-anchor cases without degrading the core accuracy cases.

This iteration pattern - eval reveals gap → tighten prompt → re-run eval → ship - is documented as a reusable skill.

**CI workflow:**

GitHub Actions workflow runs the eval harness on PRs that touch prompts or eval code. `--check` mode against baseline blocks merging if quality drops. This is the same pattern production LLM eval tools (Helicone, Langfuse) use internally.

**Frontend performance work:**

Two optimizations landed during this phase:
- Conditional SSE subscription - the EventSource connection only opens when `pending_count > 0`. Idle dashboards don't hold open SSE connections.
- Adaptive stats polling - SWR refresh interval is 5s during active processing, 30s when idle. Idle dashboards make fewer requests.

These weren't planned but were caught while reviewing production readiness.

---

## Cross-cutting decisions

Some decisions span multiple phases.

### Prompt versioning

Prompts live in `backend/app/llm/prompts/<family>/<version>.py` with the active version selected via a constant. Once a version is referenced from `llm_usage` rows, it's treated as immutable - changes go to a new version. This makes cost and quality analysis comparable across prompt iterations.

The extraction prompt evolved from v1 (initial) → v1.1 (theme naming guidance from Phase 3.4.1) → v1.2 (sentiment rules and grounded action items from Phase 5).

### Skill set and case studies

Some decisions emerged from running experiments and documenting findings. The case studies directory captures these - e.g., Case Study 7 documents the loop-aware Anthropic client cache fix, Case Study 6 patched an Opus recommendation with empirical Haiku data.

The prompt-engineering skill captures the iteration workflow: golden case rules, when to bump prompt version, how to interpret eval deltas.

### "Each commit leaves the app working"

A discipline maintained throughout. Sub-phases were preferred over single large phases specifically because each commit could leave the app in a known-working state. Breaking changes (Phase 4's switch from sync to async POST behavior, Phase 3.4.1's StatsService rewiring) were sequenced as deliberate breaking commits with clear messages.

### Locale strings, not inline copy

User-facing text lives in `frontend/src/locales/en/<feature>.ts` from Phase 1. The `i18n` infrastructure isn't strictly necessary for an English-only take-home, but the pattern matters: separation between code and copy, easier to audit, easier to localize later. The Greek CTO at the target company is a signal that this hygiene matters.

---

## Key decisions and their rationale

This section pulls out the non-obvious choices and explains the thinking. Each decision is one a different engineer could legitimately have made differently.

### Sequential batch processing instead of parallel

`POST /v1/feedback/batch` processes texts sequentially on the backend, not in parallel via `asyncio.gather`. Two reasons:

1. Anthropic rate limits (RPM and TPM) are hit faster with parallel calls. A batch of 10 in parallel can saturate the per-minute budget; sequential paces naturally.
2. The shared DB session was simpler with sequential commits. Parallel writes on a single async session create ordering and flush concerns.

After Phase 4, this is academic - each text becomes a separate Celery task and parallelism happens at the worker pool level (controlled by `concurrency=4`). The sequential batch endpoint stayed for compatibility but its purpose shifted to "dispatch N tasks" rather than "process N inline."

### Skipped sentiment distribution chart

The take-home requirement mentions "sentiment distribution." Two KPI cards (Positive %, Negative %) and the sentiment trend chart together convey the distribution data. A dedicated donut or stacked-bar chart was considered and skipped as redundant - same data, third visualization.

Documented in NOTES as a defensible choice. A 30-minute addition if reviewer feedback requests it.

### Skipped unit tests in favor of eval harness

Unit tests for pure functions (validation logic, parsing) would have been straightforward. The eval harness measures LLM output quality, which is the production signal that matters for this domain. Given a finite time budget, the eval harness was the higher-leverage investment.

The graduation path: unit tests for validate.py, extract.py error paths, and FeedbackService orchestration would total ~300 lines and 2-3 hours. Documented in NOTES.

### Postgres ILIKE instead of full-text search

Search uses `ILIKE %term%` on text and JSONB-cast columns. For hundreds of rows, this is fast enough. Full-text search (tsvector + GIN index) is graduation work.

The decision wasn't "ILIKE is good enough forever" - it was "ILIKE is right for current scale, document the upgrade path."

### Theme normalization deferred

The eval harness reveals that the LLM produces lexically different but semantically equivalent themes ("product quality", "quality", "product"). The strict theme F1 metric measures this gap explicitly.

Three approaches were considered:
- Constrained vocabulary in the prompt
- Post-extraction normalization with an aliases dictionary
- Embedding-based clustering

All three are graduation work. The current state captures all themes (no data loss) and shows them as separate entries in the chart. The eval harness baseline reflects this reality. A future prompt version or normalization layer would improve the strict F1 score without changing the data model.

### Celery Beat included (not skipped)

Initially planned to skip Beat in Phase 4, with cache warming happening on next access after expiry. Reconsidered during Phase 4 design: the marginal cost was ~30 lines and one container, and the benefit (no cold-cache slow loads for dashboard visitors) was concrete. Included.

### Heading at page level, not inside StatsDashboard

A subtle structural choice. Page headings live on pages (`app/page.tsx`), not inside child components. StatsDashboard is a section component that doesn't render its own `<h1>`. This was wrong initially (StatsDashboard had its own `<h2 text-lg>`, which read smaller than `/add` and `/feedback`'s `<h1 text-2xl>`) and corrected in Phase 4 while adding the processing pill.

The rationale: pages own page-level concerns (heading, page-level status indicators like ProcessingPill). Components own section-level concerns (the dashboard data, the form, the table). This separation makes components reusable.

### "Today" instead of "This week" for the time-bucketed KPI

Late change in the dashboard upgrade. "This week" sounds like a rolling 7-day window, but most users mentally compare "today" to "yesterday" for trend signals. Switched to a same-day comparison with day-over-day delta. Better trend signal for daily-cadence feedback.

---

## What's intentionally not in this project

Some things were considered and deliberately left out. Documented here so the absence is read as a choice, not an oversight.

- **CSV file upload.** The paste form supports multi-line text input which covers the immediate use case. Real CSV upload (with column mapping) is documented in NOTES as future work. The "Bulk upload" copy was tightened to "CSV file upload is on the roadmap."
- **Real-time charts.** Charts auto-refresh via SWR's polling cadence. They don't redraw on SSE events. The per-row table updates were the higher-leverage real-time win; chart real-time would have been ~2 hours of additional work for marginal benefit.
- **Authentication / multi-tenancy.** Single-tenant by design. Auth would be a Phase 6+ concern.
- **Persistent user preferences.** Search and filter state lives in React useState, not URL params. Refresh loses the search. Acceptable for the analyst workflow; a graduation path would use Next.js search params.

---

## On the engineering process itself

Several themes ran through the build:

**Decisions before code.** The hardest part of each sub-phase was getting the design right before writing it. Once decisions were locked, the implementation was mechanical. The phases where I rushed into implementation before nailing the design (early Phase 2's single-page layout, early Phase 3.4's missing cost tracking) are the ones I had to revisit.

**Reading the requirements word by word.** "Searchable" is not "filterable." "Distribution" implies a chart, not two KPI numbers. Re-reading the spec at the boundary of each phase caught gaps that would have shipped otherwise. Phase 3.2.2 (search) and the sentiment distribution analysis came from these re-reads.

**Catching gaps at the right time.** When I noticed the dashboard heading was a different size from other pages (mid-Phase 4 work), I didn't pause to ship a fix-up phase - I rolled the heading fix into the already-in-flight Phase 4 work that was touching the dashboard. Similarly, the layout consistency audit in Phase 3.2.1 happened during multi-paste work, not as a separate phase. Bundling related changes kept the phase count manageable.

**Pre-empting refactor cost.** The decision to skip a progress bar UI in Phase 3.2.1 (multi-paste) anticipated that Phase 4's async refactor would replace the model entirely. Building a sync progress bar would have been throwaway work. The toast UX (submit confirmation, completion confirmation) works in both sync and async modes. Same UI, different semantics, no rewrite needed when Phase 4 landed.

**Iteration where iteration was warranted.** The chart implementation in Phase 3 went through three rounds. Each round produced a real concern that the previous didn't surface. Some things you can't plan ahead - you have to ship a version, look at it, and iterate. The phasing approach made this safe: revert to the last commit if needed, ship the next iteration cleanly.

---

## Looking back

Was the phasing right? Mostly. Two adjustments I'd make next time:

1. **Eval harness earlier.** Building it in Phase 5 was late. If it had landed in Phase 2 (after extraction worked but before the dashboard), prompt iteration could have started immediately and Phase 4's worker would have been fed a more reliable prompt. The trade was reasonable - build the product first, evaluate after - but earlier eval would have caught the v1.1 sentiment regressions sooner.

2. **Audit table from the start.** The `llm_usage` table in Phase 3.4.1 was retrofitted into a codebase that already had `Feedback.llm_metadata`. Doing it right from Phase 2 would have avoided the migration. The retrofit was clean enough that this is a minor regret, not a major one.

What worked well:

- **Sub-phase sizing.** Most sub-phases were 3-7 commits. Small enough to ship in one sitting, large enough to be coherent.
- **Verification at each commit.** Each commit ended with a verify-it-works step. This caught regressions immediately rather than letting them accumulate.
- **Deferring CSV upload.** Multi-paste text input covers 90% of the use case. Real CSV upload is a 2-3 hour addition that wasn't justified by the take-home's scope. Documented as future work.
- **Locking design decisions before writing.** Most phases had a clarifying conversation with myself (and via design notes) before any code. The design alignment time was non-trivial but it kept commit count down and shippability up.

The project is in a state I'm comfortable submitting. It has the features the spec asks for, plus async processing as a bonus production-grade tier, plus an eval harness that gates prompt quality, plus documentation explaining the engineering thinking. The git history reads as deliberate engineering, not as a code dump.