# Notes for reviewers

## Context-engineering decisions I'm proudest of

**1. Scoped memory, not one giant CLAUDE.md.** Root `CLAUDE.md` stays
short — it imports `@.claude/context/architecture.md` for system shape
and points at two stack files. Real conventions live in
`backend/CLAUDE.md` and `frontend/CLAUDE.md`, auto-loaded only when
Claude reads files in those directories. The prompt-iteration workflow
lives in the `prompt-engineering` skill and loads on invoke, not per
turn. Net effect: any given turn, Claude sees only the context relevant
to the files in play — backend gotchas don't blow tokens on a frontend
edit, the eval workflow doesn't blow tokens on a docs read.

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

**The stress-tester subagent that earned nothing.** Built a 215-line
`stress-tester.md` early — orchestrator for `stress_test.sh` +
diagnostic SQL + cost gates. Never invoked it across the build; main
Claude just ran the script and queries inline. Deleted it
(commit `95a1708`). Same lesson surfaced when I dropped two speculative
skills (`backend-patterns`, `llm-workflow`) for duplicating CLAUDE.md.
A subagent or skill earns its slot only when actually invoked AND
non-trivial to inline. Speculative scaffolding is harness bloat.

**The 429 retry-knob rabbit hole ([Case Study 8](./CASE_STUDIES.md#case-study-8--the-429-retry-knob-rabbit-hole-rediscovering-cs6-the-hard-way)).**
100-item burst left 24 tasks `FAILED`. Knee-jerk: tune retries. Three
tweaks shrank failures 24 → 5, never to zero. Real fix:
`CELERY_WORKER_CONCURRENCY=3 → 1`. Math from [CS6](./CASE_STUDIES.md#case-study-6--anthropic-rate-limits-vs-worker-concurrency)
already said `3 × 2s × 1.5k tokens ≈ 90k tok/min vs 50k TPM cap`.
Retries spread failures over time; they don't change the rate. Lesson:
when retry-tuning shrinks failures monotonically but never to zero,
stop tuning and recompute upstream rate against the cap.

## What I'd add to the harness if this were long-lived

- Golden set + evaluator for the summary prompt — only extraction
  has one today.
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
shortcut warranted them. Calling out per the PDF.
