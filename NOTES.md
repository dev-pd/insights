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

**2. The prompt iteration triplet: harness + sub-agent + skill.** The
eval harness runs 20 hand-curated goldens with `--check` exit codes for
CI gating. The `prompt-evaluator` sub-agent does ONE thing — run the
harness, report pass/fail vs baseline — with threshold tables and file
paths baked into the prompt, not delegated to the model. The
`prompt-engineering` skill owns the meta-workflow (when to bump versions,
how to write goldens, when to update baselines). Different lifecycles,
clean boundaries. I also added an `explore_edges.py` probe to SEE
behavior on candidate inputs before encoding expectations into a golden
— commit `1257442` shows the full v1.1→v1.2 loop with metric deltas.

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
- A `UserPromptSubmit` hook that injects relevant CASE_STUDIES entries by
  keyword — auto-prevents rediscovering past bugs.
- A drift-checker that diffs CLAUDE.md claims (API paths, folder layout,
  Settings field names) against the actual code. Mechanical staleness is
  the easiest kind to ship by accident as the codebase moves under you.
- Real CI spend monitoring on the eval workflow.

**On hooks/slash commands:** I didn't write any. The take-home scope had
no recurring event-driven trigger that warranted a hook, and no
muscle-memory shortcut that warranted a slash command. Per the PDF's
"call it out rather than reach for them for show" — calling it out.
