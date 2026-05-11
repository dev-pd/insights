# Notes for reviewers

## Context-engineering decisions I'm proudest of

**1. Scoped memory, not one giant CLAUDE.md.** Root `CLAUDE.md` points
at scoped files. Real conventions live in `backend/CLAUDE.md` and
`frontend/CLAUDE.md`, auto-loaded only when Claude reads files in that
directory. The `prompt-engineering` skill carries the iteration workflow
and loads on invoke. Deleted two intermediate skills mid-project once
content drifted toward generic patterns or duplicated CLAUDE.md — a
skill earns its slot only when content is project-specific AND not
derivable from auto-loaded CLAUDE.md.

**2. A two-agent prompt-iteration loop with a baseline gate.**
`edge-case-generator` proposes JSONL candidates for gaps;
`prompt-evaluator` re-runs the goldens and gates on `baseline.json`.
Seven rounds. Round 6 tried a regex validator (too brittle) and a
"distill into generic action item" rule (silently inflated the
negative count). v1.7's fix was structurally interesting: an `is_noise`
field on the schema — give the model a new output channel rather than
tightening prompt rules. Each piece has thresholds, paths, and decision
criteria baked in.

**3. `CASE_STUDIES.md` as a separate decision log.** Production-shaped
incidents live in a dedicated log; CLAUDE.md gotchas cross-reference it.
Keeps CLAUDE.md tight without losing the "why."

## What didn't work, and what I changed

**The Case Study 7 fix that wasn't a fix.** First attempt cached the
Anthropic client keyed by `id(loop)`. Passed manual smoke test. A
30-item stress run caught it: 29/30 tasks still emitted
`llm_transient_retry`. CPython recycles addresses; `asyncio.run()` per
task creates+closes+GCs a loop each time, so the new loop kept getting
the same `id()`. Switched to `is`/`is not` and the warning rate hit
zero. Lesson: declaring a fix needs evidence, not just "looks right."

**The 429 retry-knob rabbit hole (Case Study 8).** A 100-item burst
left 24 tasks `FAILED`. Knee-jerk: tune retries. Three tweaks shrank
failures 24 → 5, never to zero. Real fix: `CELERY_WORKER_CONCURRENCY=3 → 1`.
Math from CS6 already said `3 × 2s × 1.5k tokens ≈ 90k tok/min vs 50k
TPM cap`. Retries spread failures over time; they don't change the
average rate. Lesson: when retry-tuning shrinks the failure count
monotonically but never to zero, stop tuning and recompute the upstream
rate against the cap.

## What I'd add to the harness if this were long-lived

- Golden set + evaluator for the summary prompt — extraction has one;
  summary regressions are eyeballed today.
- `/prompt-bump` slash command — scaffold next version file, flip
  `ACTIVE_*`, print rebuild-both-images reminder.
- `/golden-add` — accept/edit a candidate, append to golden JSONL.
- Pre-commit hook on `app/llm/prompts/**` — refuses commit on baseline
  regression.
- `harness-doc-drift` checker — diffs CLAUDE.md claims (paths, Settings
  names) against the codebase.
- `/cost-week` slash command — summarizes the `llm_usage` table by
  `call_type` + `prompt_version` for the last 7 days; surfaces spend
  drift after a prompt bump.
- MCP to an issue tracker — `status=failed` rows one-click ticketable,
  pre-filled with prompt version + llm_metadata.

**On hooks/slash commands:** none used. No recurring trigger or
muscle-memory shortcut warranted them. Calling out per the PDF.
