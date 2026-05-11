---
name: prompt-engineering
description: Workflow for iterating prompts in backend/app/llm/prompts/ — versioning, golden cases, eval harness, baseline updates. Invoke when editing prompts, after an eval regression, or when adding golden cases.
---

# Prompt engineering workflow

Everything about iterating prompts in this codebase: versioning, evals, baselines, what to change vs leave alone, and how to keep traces reproducible.

## Where things live

```
backend/app/llm/prompts/
├── extraction/           __init__.py + v1.py, v1_1.py, v1_2.py (ACTIVE)
└── summary/              __init__.py + v1.py, v1_1.py

backend/evals/
├── golden/extraction.jsonl    Hand-curated test cases
├── run_evals.py               Async harness (JSON + --check)
├── baseline.json              Thresholds + last-observed metrics
└── explore_edges.py           Ad-hoc probe (no grading)

.claude/agents/prompt-evaluator.md   Sub-agent that runs the harness
.github/workflows/evals.yml          CI gate (triggers on prompts/ or evals/ PRs)
```

## The iteration loop

1. **See a failure.** Either real output looks wrong, OR a new golden fails on the active prompt. For exploratory candidates, run `explore_edges.py` first to see actual behavior before encoding expectations.
2. **Add/update a golden** capturing the failure BEFORE editing the prompt. Makes the fix measurable and prevents future regressions.
3. **Create a new version file** (`extraction/v1_3.py`). DO NOT edit a previous version — they're immutable so production traces stay reproducible. Set `VERSION = "extraction/v1.3"`. Copy the previous prompt, make the targeted change.
4. **Point ACTIVE** at the new version in `extraction/__init__.py` (two lines: `ACTIVE_PROMPT`, `ACTIVE_VERSION`).
5. **Rebuild + eval.** `docker compose build backend` (image bakes the prompt), then run the harness via `docker compose run --rm -v "$(pwd)/backend/evals:/app/evals:ro" backend python /app/evals/run_evals.py` — or invoke the `prompt-evaluator` sub-agent.
6. **Analyze.** Did the targeted metric improve? Anything regress? If improved → commit everything together (see below). If regressed → revert ACTIVE in `__init__.py`, iterate on the new version file in place (it's not committed yet, so still mutable) or scrap and bump.

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

## See also

- `backend/CLAUDE.md` — overall backend conventions
- `.claude/skills/llm-workflow/SKILL.md` — broader LLM call infrastructure (retries, cost tracking, tool use)
- `.claude/agents/prompt-evaluator.md` — the sub-agent that runs the harness for you
- `CASE_STUDIES.md` — incidents that informed prompt design (Case Study 7's loop-identity bug was prompt-adjacent — found via the eval-style observation pattern)
