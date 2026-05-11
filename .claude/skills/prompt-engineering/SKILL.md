---
name: prompt-engineering
description: Workflow for iterating prompts in backend/app/llm/prompts/ — versioning, golden cases, eval harness, baseline updates. Invoke when editing prompts, after an eval regression, or when adding golden cases.
---

# Prompt engineering workflow

Everything about iterating prompts in this codebase: versioning, evals, baselines, what to change vs leave alone, and how to keep traces reproducible.

## Where things live

```
backend/app/llm/prompts/
├── extraction/           __init__.py + v1.py, v1_1.py, v1_2.py, v1_3.py (ACTIVE)
└── summary/              __init__.py + v1.py, v1_1.py, v1_2.py (ACTIVE)

backend/evals/
├── golden/extraction.jsonl    Hand-curated test cases (~40)
├── run_evals.py               Async harness (JSON + --check + --report-path)
├── baseline.json              Thresholds + last-observed metrics
├── explore_edges.py           Ad-hoc probe (no grading)
└── reports/                   Persisted JSON reports per run (`<UTC>-<version>.json`)

.claude/agents/prompt-evaluator.md   Sub-agent that runs the harness
.github/workflows/evals.yml          CI gate (triggers on prompts/ or evals/ PRs)
```

Only `extraction/` has a golden set today. `summary/` is verified qualitatively via the dashboard widget; adding a summary golden set is listed in NOTES.md as graduation work.

## The human-minimal loop (preferred)

Three roles, three terminals: edge-case-generator, prompt-evaluator, and main Claude (the strategist). Files on disk are the only shared state. **The human only types 4-5 supervision prompts per round.**

```
┌──────────────────┐    writes      ┌──────────────────────────────┐
│ edge-case-       ├──────────────►│ golden/                       │
│ generator        │                │   extraction.candidates.jsonl │
└──────────────────┘                └──────────────────────────────┘
                                              │
                                              │ reads
                                              ▼
┌──────────────────┐    writes      ┌──────────────────────────────┐
│ prompt-          ├──────────────►│ reports/                      │
│ evaluator        │                │   <UTC>-<version>.json        │
└──────────────────┘                └──────────────────────────────┘
                                              │
                                              ▼ reads
                                       ┌─────────────┐
                                       │ main Claude │ ←──→ human
                                       │ (diagnose)  │      (decide)
                                       └─────────────┘
```

### What the human types (literally)

**Terminal A (edge-case-generator session):**
> "Generate adverse candidates for the current prompt. Write to the candidates file."

The agent reads goldens + active prompt + validator + schema, writes 5-7 candidates to `backend/evals/golden/extraction.candidates.jsonl`, emits a summary to stdout. Done in ~30s.

**Terminal C (main Claude session — the diagnostician):**
> "Edge-case-generator wrote new candidates. Read the file, tell me if any look broken or duplicate."

Main Claude reads the file, evaluates realism / single-failure-mode / unambiguity / coverage delta, flags any candidates to drop or refine. Human approves or edits.

**Terminal B (prompt-evaluator session):**
> "Edge-case-generator has generated new candidates. Check the candidates file, run the eval, save the report."

Agent runs the harness with `--golden-path /app/evals/golden/extraction.candidates.jsonl --check --report-path /app/evals/reports/AUTO`. Returns a PASS/FAIL summary to stdout AND writes the JSON report to disk. ~10s.

**Terminal C (back to main Claude):**
> "Prompt-evaluator just wrote a report. Read the latest file in evals/reports/, walk me through the failures."

Main Claude reads the report, categorizes each failure (golden overspec vs prompt gap vs LLM flake), proposes refinements or a v1.X prompt bump. Human decides.

**Terminal C (commit step, still main Claude):**
> "OK, proceed: [refine these goldens / write v1.X with this rule / both]. Then merge approved candidates into the main goldens, delete the candidates file, rebuild backend+worker, re-run prompt-evaluator on the full suite. If all metrics ≥ baseline, update baseline.json + commit everything together."

Main Claude executes. Round complete.

### When to update what

| Trigger | Update |
|---|---|
| Candidates land in goldens | `backend/evals/golden/extraction.jsonl` (append, then delete candidates file) |
| Prompt rule changes | New `extraction/v<N>.py` file + bump ACTIVE in `__init__.py` (NEVER edit a released version) |
| Metrics observably improve | `baseline.json` — both `observed_at_baseline` (always) AND `thresholds` (raise the floor; keep 5-8pp buffer for LLM variance) |
| New edge-case pattern entered the goldens | `frontend/src/locales/en/addFeedback.ts` `edgeCases.cases` list (mirror what graders see in the harness) |
| Round produces a v1.X | `NOTES.md` section 2 (one-line addition referencing the round, what got hardened) |
| Anything material changed in the harness shape | `backend/CLAUDE.md` Async-processing-or-LLM-relevant gotcha section, if applicable |

### Per-round commit shape

When a round produces a new prompt version, **one atomic commit** contains all of:
- The new `extraction/v<N>.py` (immutable from now on)
- `extraction/__init__.py` ACTIVE bump
- Refined / new goldens in `extraction.jsonl`
- Updated `baseline.json` (observed + thresholds)
- The two latest reports in `evals/reports/` (the before-v<N> and after-v<N> runs)
- `NOTES.md` section 2 one-line update
- (If new edge-case patterns entered) `frontend/src/locales/en/addFeedback.ts` updated

Commit message body MUST include the metric deltas in a small table — that's the audit trail.

## The legacy iteration loop (still valid for manual work)

The human-minimal flow above is the preferred path. The manual sequence is:

1. **See a failure** OR proactively widen coverage with `explore_edges.py` for ad-hoc probes.
2. **Add/update a golden** capturing the failure BEFORE editing the prompt.
3. **Create a new version file** (`extraction/v<N>.py`). DO NOT edit a previous version.
4. **Point ACTIVE** at the new version in `extraction/__init__.py`.
5. **Rebuild backend + worker** (both build from `./backend`; worker has its own image): `docker compose build backend worker`.
6. **Run prompt-evaluator** or the harness directly: `docker compose run --rm -v "$(pwd)/backend/evals:/app/evals" backend python /app/evals/run_evals.py --check --report-path /app/evals/reports/AUTO`.
7. **Analyze.** If improved → commit everything together (above). If regressed → revert ACTIVE in `__init__.py`, iterate on the new version file in place, try again.

## What "commit everything together" means

When a new prompt version observably beats the baseline, **one commit** contains:
- The new version file (`extraction/v1_2.py`)
- The `__init__.py` ACTIVE bump
- `baseline.json` updated: `observed_at_baseline` reflects the new run, `thresholds` raised so the new floor is the new minimum
- Any new golden cases added during diagnosis

Commit message body should include the metric deltas:
```
sentiment_accuracy:     86.7% → 92.0%  (+5.3pp)
theme_subset_pass_rate: 75.0% → 80.0%  (+5.0pp)
overall_pass_rate:      66.7% → 75.0%  (+8.3pp)
```

This makes the improvement claim auditable in `git log`.

## Adding a golden case

Open `backend/evals/golden/extraction.jsonl`. Append one JSON object per line:

```json
{
  "id": "stable-identifier-no-spaces",
  "text": "The verbatim feedback text. Keep realistic-length (10-500 chars).",
  "expected_sentiment": "positive|neutral|negative",
  "expected_themes_subset": ["term1", "term2"],
  "expected_themes_max_count": 4,
  "expected_action_items_required": true,
  "expected_language": "en",
  "notes": "Why this case exists. What it catches that the existing 15 don't."
}
```

### Notes on each field

**`expected_themes_subset`** uses substring matching (case-insensitive). `"shipping"` matches `"shipping speed"`, `"slow shipping"`, etc. **Pick lenient anchors** — a strict exact-match expectation will false-negative when the model paraphrases. Empty list `[]` skips this check (useful for very terse cases where any 1-3 themes are reasonable).

**`expected_themes_max_count`** is the upper bound. Prompt allows up to 5; some cases should yield fewer (e.g., 2 for a single-issue complaint).

**`expected_action_items_required`** is presence/absence — we DO NOT match exact action text (too brittle, paraphrased every time). Set `true` for cases that clearly demand a change ("please fix X", "would love Y") and `false` for pure praise/observation.

**`expected_language`** is ISO 639-1. Most cases are `"en"`. Add non-English cases sparingly — they're useful for catching language-detection regressions but burn the same Anthropic budget as English cases.

**`notes`** explains *why this golden exists*. Future-you reads it when a case fails and asks "do I fix the prompt or the golden?".

### When the golden disagrees with the model

Sometimes the model is right and the golden is wrong (or just overly specific). Example from the baseline run: the `multi-theme-bug` golden expected `["shipping", "support"]` but the model returned `["shipping", "customer service", "quality"]`. The model's `customer service` is semantically equivalent to `support`. Two paths:

1. **Adjust the golden** to use a substring that matches both ("service" matches both "support" and "customer service")
2. **Adjust the prompt** to push canonical-name discipline harder (the v1.1 rule already says "use 'service' instead of 'customer service team'" — apparently not strong enough)

Usually it's a mix of both. Don't auto-update goldens to match every model output — that defeats the eval. Update only when the golden was genuinely too restrictive.

## Interpreting eval output

### The metrics (from `run_evals.py`)

| Metric | What it measures | When it fails |
|---|---|---|
| `sentiment_accuracy` | Exact sentiment match | Edge cases with mixed/ambiguous tone. Sentiment with feature suggestion ("would love X") often slips between positive/neutral. |
| `theme_subset_pass_rate` | Every expected term substring-matched | Synonym mismatch ("support" vs "customer service"), missed concepts. |
| `theme_count_pass_rate` | Returned ≤ max_count | Over-extraction (model returns 5 when 2 expected). |
| `action_items_pass_rate` | Presence/absence match | Hallucinated actions on praise, OR missed actions on implied requests. |
| `language_accuracy` | ISO code exact | Rare; non-English text not detected. |
| `overall_pass_rate` | % passing ALL applicable checks | Composite — high bar, useful for "is the prompt fundamentally working". |

### Reading a failure

```
- multi-theme-bug: themes_subset
    themes_subset: expected=['shipping', 'support'] actual=['shipping', 'customer service']
```

Decompose:
- `multi-theme-bug` is the golden ID — look at the case definition in `extraction.jsonl`
- `themes_subset` is the failing check
- Expected `['shipping', 'support']` — both required, substring-match
- Actual `['shipping', 'customer service']` — `shipping` matched, `support` did NOT (because `"support"` is not a substring of `"customer service"`)

Now decide: change the prompt (push canonical name harder), change the golden (relax the substring), or both?

## What NOT to do

- **Do not edit a released version file in place.** `v1_1.py` is immutable. Every change creates a new version. The whole point is that `llm_usage.prompt_version="extraction/v1.1"` traces from production should reproduce against the exact file content on disk forever.

- **Do not run evals against a model different from the production one.** `LLM_MODEL` controls which model the harness scores against. Same prompt scores differently on Haiku vs Opus vs Sonnet — the baseline thresholds are tied to a specific model. Switching models requires re-baselining.

- **Do not auto-generate goldens with an LLM.** Goldens are the spec. Auto-generated cases just measure "does the model agree with itself" — useless. Hand-curate.

- **Do not relax thresholds to make a bad prompt pass.** If the new prompt regresses, fix or revert. Lowering thresholds without a corresponding behavior change is the same as deleting the eval.

- **Do not run the full eval on every commit.** Costs ~$0.005 on Haiku, ~$0.30 on Opus. The CI workflow already gates on `prompts/` or `evals/` file changes. Local runs are dev-time only.

- **Do not commit prompts without running the eval first.** Always run before committing the `__init__.py` ACTIVE bump.

## Traps

### Forgetting to rebuild the backend image after editing a prompt

The eval harness invokes `extract_insights` from inside a one-off backend container (the only environment with `ANTHROPIC_API_KEY` loaded via `env_file`). The container uses the **already-built** `insights-backend:latest` image — it does NOT mount the host's `backend/app/` source. So if you edit a prompt file and run the eval without rebuilding, you score the OLD prompt and the report still says `prompt_version: extraction/v1.X` (the previous active one) — which is a particularly confusing failure mode because the file on disk says the new one.

The fix is one command, run after every prompt edit:

```bash
docker compose build backend && \
  docker compose run --rm -v "$(pwd)/backend/evals:/app/evals:ro" \
  backend python /app/evals/run_evals.py
```

Symptom that you forgot: the `prompt_version` field in the eval report doesn't match the `ACTIVE_VERSION` in `extraction/__init__.py`. Always sanity-check the first line of the eval output.

The `evals/` directory IS mounted (`-v ... :ro`), so changes to goldens and the harness itself pick up without a rebuild. Only `app/` requires the rebuild.

## Cost notes

| Model | Per eval run (15 goldens) |
|---|---|
| `claude-haiku-4-5` | ~$0.005 |
| `claude-sonnet-4-6` | ~$0.05 |
| `claude-opus-4-7` | ~$0.30 |

The harness is single-threaded (sequential) — Anthropic rate limits absorb easily at 15 cases × ~1.5s/case ≈ 25s wall clock for Haiku. Bumping to 50 goldens triples cost and wall clock proportionally.

## Common iteration patterns

### Pattern 1: targeted sentiment fix

You see a class of cases ("would love to see X" type feature requests) being misclassified as positive instead of neutral. The fix is a one-line prompt addition:

```
Sentiment guidelines:
  - Classify polite feature suggestions ("would love X", "could you Y") as
    neutral, not positive — enthusiastic language doesn't make a request
    into praise.
```

Add 2-3 golden cases covering this class, bump the version, run the eval, check the sentiment_accuracy delta.

### Pattern 2: theme consistency push

You see `theme_subset_pass_rate` failing because the model uses near-synonyms inconsistently ("support" / "customer service" / "service team"). The v1.1 prompt already pushes canonical names, but not strongly enough. Add stronger examples:

```
Theme canonicalization (STRICT):
  - "customer service", "service team", "support staff" → "support"
  - "shipping speed", "delivery time", "shipping delays" → "shipping"
  - "pricing tiers", "plan pricing", "subscription pricing" → "pricing"
```

### Pattern 3: action-item hallucination

The model invents action items for pure praise ("Great product!" → action: "continue to manufacture great products"). The fix:

```
Action items — return ONLY when the feedback names a specific, concrete
change the company should make. Do NOT return action items for praise,
generic positive feedback, or vague suggestions without a clear ask.
```

## The full generator → evaluator loop

For proactive coverage improvement (not just reactive bug-fixing), the two sub-agents form a pipeline:

```
edge-case-generator → human review → append to goldens → prompt-evaluator → metric report
                                                                                  │
                                                                                  ▼
                                                  pass    fail
                                                   │       │
                                                   ▼       ▼
                                                commit   iterate prompt → loop
```

`edge-case-generator` reads the existing goldens + active prompt and emits JSONL candidates covering gaps it finds in the coverage taxonomy. It NEVER writes files — a human picks which candidates to keep. Selected lines get appended to `extraction.jsonl`. `prompt-evaluator` then runs the eval to see whether the live prompt already handles them. If everything still passes the baseline, the new goldens lock in current behavior; if anything fails, that's the signal to iterate the prompt (back to step 3 of the iteration loop).

## See also

- `backend/CLAUDE.md` — overall backend conventions
- `.claude/skills/llm-workflow/SKILL.md` — broader LLM call infrastructure (retries, cost tracking, tool use)
- `.claude/agents/edge-case-generator.md` — proposes new goldens (proposal half of the loop)
- `.claude/agents/prompt-evaluator.md` — runs the eval against the active prompt (validation half)
- `CASE_STUDIES.md` — incidents that informed prompt design (Case Study 7's loop-identity bug was prompt-adjacent — found via the eval-style observation pattern)
