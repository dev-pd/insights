# Notes for reviewers

## Context-engineering decisions I'm proudest of

**1. Scoped memory + on-demand skills, not one giant CLAUDE.md.** The root
CLAUDE.md points at scoped files rather than dumping. Real conventions
live in `backend/CLAUDE.md` and `frontend/CLAUDE.md`, which auto-load
only when Claude reads files in that directory. Two skills
(`prompt-engineering`, `llm-workflow`) carry the deep patterns and load
on invoke, not per turn. `@.claude/context/architecture.md` is imported
into the root for shared system shape. I deleted a third skill
(`backend-patterns`) mid-project once its content drifted toward generic
Python/FastAPI patterns Claude can infer from the codebase — a skill
only earns its slot when the content is genuinely project-specific.

**2. A full prompt-iteration pipeline: generator → evaluator → human →
golden set.** Two narrow sub-agents form the loop. `edge-case-generator`
proposes JSONL candidates for gaps; `prompt-evaluator` runs the eval,
writes a timestamped JSON report to `evals/reports/`, reports pass/fail
vs `baseline.json`. The loop ran three rounds across 20 candidates —
all three playbook outcomes surfaced: most passed cleanly (prompt held),
three forced golden refinements (overspecified subsets), and one
exposed a real over-extraction weakness that v1.4 fixed with a new
"one-topic discipline" rule. 20 → 40 goldens, v1.3 → v1.4,
`overall_pass_rate` 80% → 95%. Each piece has thresholds, file paths,
and decision criteria baked in rather than punted to the model.

**3. `CASE_STUDIES.md` as a separate decision log.** Production-shaped
incidents (Anthropic rate-limit ceiling, asyncio event-loop binding bug,
dispatch-before-commit race) live in a dedicated log. CLAUDE.md gotcha
sections cross-reference it. Keeps CLAUDE.md tight without losing the
"why" behind surprising design choices.

## What didn't work, and what I changed

**The Case Study 7 fix that wasn't a fix.** First attempt cached the
Anthropic client keyed by `id(asyncio.get_running_loop())` — passed my
manual smoke test, looked right on paper. A 30-item Haiku stress test
(run via the `stress-tester` sub-agent) caught it: 29 of 30 tasks still
emitted `llm_transient_retry`. CPython recycles memory addresses when
objects are GC'd; `asyncio.run()` per Celery task creates+closes+GCs a
loop each time, so the new loop kept getting the same `id()` and the
cache miss never fired. Switched to object identity (`is`/`is not`) and
the warning rate went to zero. Lesson, encoded in `client.py:get_client()`
as a comment: declaring a fix needs evidence, not just "looks right."

## What I'd add if this were long-lived

- A golden set for the summary prompt (currently only extraction has one).
- An automated "generate → eval → diff → file PR" cron loop on top of
  the existing two-agent pipeline.
- A drift-checker that diffs CLAUDE.md claims (API paths, folder layout,
  Settings field names) against the actual code.
- Real CI spend monitoring on the eval workflow.

**On hooks/slash commands:** I didn't write any. The take-home scope had
no recurring event-driven trigger that warranted a hook, and no
muscle-memory shortcut that warranted a slash command. Per the PDF's
"call it out rather than reach for them for show" — calling it out.
