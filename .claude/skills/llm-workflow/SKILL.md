---
name: llm-workflow
description: LLM call internals for backend/app/llm/ — tool-use extraction with Pydantic schemas, the call_with_retry wrapper, cost controls, failure-mode taxonomy. Invoke when editing extract.py, summarize.py, client.py, validate.py, or schema.py. For prompt iteration use the prompt-engineering skill instead.
---

# LLM workflow

LLM-specific patterns under `backend/app/llm/`. The module is a bounded context: no HTTP, no DB, plain text in / Pydantic out. Lifts cleanly into a host codebase.

## Module map

```
backend/app/llm/
├── client.py     AsyncAnthropic singleton + call_with_retry wrapper
├── extract.py    extract_insights() — tool-use extraction
├── summarize.py  generate_summary() — prose summary over many rows
├── schema.py     ExtractionResult Pydantic model
├── validate.py   is_processable() — pre-LLM cheap-rejection filter
└── prompts/
    ├── extraction/  immutable versioned files + __init__ ACTIVE selector
    └── summary/     same layout
```

**Read the real files for code.** This skill documents the *why* — the file itself is the canonical *what*.

## Tool use as extraction (not freeform JSON)

`extract.py` uses Anthropic's tool-use API with `tool_choice={"type": "tool", "name": "extract_insights"}` to force a structured response. Three reasons:

1. Anthropic's API constrains the tool input to match `input_schema` — freeform JSON has no such guarantee.
2. No parsing gymnastics (no markdown fences, no "Here's the JSON:" preambles).
3. Pydantic round-trip: one model → derive JSON schema → validate the response back. Single source of truth.

Schema is in `app/llm/schema.py` (`ExtractionResult`, `extra="forbid"`). Field `description` strings are read by Claude as part of the prompt — write them like instructions to a human annotator.

**Forced tool name must match the `tools=[...]` entry exactly.** Use the `TOOL_NAME` constant — symptom of mismatch: `LLMSchemaError("No extract_insights tool_use in response")`.

## Pre-LLM validation

`validate.py:is_processable()` runs BEFORE the API call. Returns `SkipReason | None`:

| Rule | Skip reason | Why |
|---|---|---|
| Stripped length < `feedback_min_length` | `TOO_SHORT` | "ok", "good" carry no signal |
| Stripped length > `feedback_max_length` | `TOO_LONG` | Cost cap; long pastes are usually spam/logs |
| Alpha ratio < `feedback_min_alpha_ratio` | `LOW_ALPHA_RATIO` | Mostly punctuation/numbers |
| No 3+ consecutive Latin letters | `NO_WORDS` | Keyboard mashing |
| `better_profanity` hit | `PROFANITY_DETECTED` | Optional filter |

Skipped vs failed:
- `status="skipped"` — rejected by validator, no LLM call, cheap.
- `status="failed"` — passed validator, failed during LLM extraction, paid for the call.
- Both saved with `skip_reason`. Transparency over silent rejection.

## The call_with_retry wrapper

`client.py:call_with_retry()` owns the retry loop because we want structured per-error-class logs. The Anthropic SDK's built-in retries are disabled (`max_retries=0` on `AsyncAnthropic`). Don't re-enable them.

Behavior:
- **Retries** on `APITimeoutError`, `APIConnectionError`, 429, 5xx. Exponential backoff with jitter.
- **Does NOT retry** on 4xx other than 429 — those are our bug, not transient.
- **Bounded concurrency** via module-level `asyncio.Semaphore(settings.llm_concurrency_limit)`.
- **Per-call timeout** from Settings, passed to the SDK's native `timeout` parameter.
- **Structured logs** every call: `prompt_version`, `input_length`, `latency_ms`, `input_tokens`, `output_tokens`, `attempt`.
- **Error mapping** to typed exceptions: `APITimeoutError → LLMTimeoutError`, 429 → `LLMRateLimitError`, 5xx → `LLMError`, schema mismatch → `LLMValidationError`.

**`APIConnectionError` lacks `status_code`** — use `getattr(e, "status_code", None)`. Treat `None` as transient.

## Event-loop binding

`get_client()` caches `AsyncAnthropic` per asyncio loop using **object identity** (`is`/`is not`), NOT `id(loop)`. CPython recycles addresses across GC'd loops, and asyncio.run() in Celery tasks creates+closes+GCs a loop per task — id-based caching missed every rebuild. See Case Study 7 in `CASE_STUDIES.md`. Don't rewrite this back to id().

The backend (one long-lived loop) sees the check as a no-op. Workers (asyncio.run per task) hit the rebuild path on every task — but rebuilding the client is cheap (no DNS/TLS until first call) so this is fine.

## Cost controls

| Lever | Knob | Notes |
|---|---|---|
| Model | `LLM_MODEL` | Default `claude-haiku-4-5` (~$1/$5 per MTok). Haiku handles extraction well. |
| Output cap | `llm_max_tokens` | Extraction output is ~200 tokens; cap prevents runaway. |
| Input cap | `feedback_max_length` | Validator rejects longer; saves input tokens. |
| Pre-validation | `is_processable` | ~10-20% of real submissions fail validation, all saved API calls. |
| Concurrency | `llm_concurrency_limit` | Bounds parallel burst, stays under Anthropic RPM. |
| Retry budget | `llm_max_retries`, `celery_extract_max_retries` | Backoff so we don't hammer when 429'd. |

Production levers documented in NOTES.md as graduation work: per-user limits, daily spend caps, dynamic batching, prompt caching.

## LLM usage audit table

Every successful API call (extraction or summary) writes one row to `llm_usage` (see backend/CLAUDE.md § LLM usage audit). Single source of truth for cost, latency, and per-prompt-version analytics — used by the eval workflow when comparing prompt versions, and the obvious place to add a cost dashboard later.

## Failure handling categories

**Transient (retried inside `call_with_retry`):** network timeout, 429, 5xx. Caller never sees these unless retries exhaust.

**Schema validation (retried once in `extract.py`):** model returned a tool call but the input fails Pydantic validation (rare with forced tool_use). Retry once with the same input. If it fails again → `LLMValidationError`, row marked `failed` with `skip_reason="llm_validation_error"`.

**Terminal (failed):** auth errors, 4xx non-429, retries exhausted. Row marked `failed`. User sees the failed status; logs have detail.

## Multi-language

The model is multilingual — no separate prompts per language. Language is extracted as part of the structured output (ISO 639-1). The validator's "3+ Latin letters" rule has a Latin bias (Spanish/French/German pass, Cyrillic/Arabic/CJK fall through to TOO_SHORT/LOW_ALPHA). Production graduation: per-language eval sets + language-specific validation.

## See also

- `.claude/skills/prompt-engineering/SKILL.md` — how to iterate prompts, write goldens, interpret eval output. Invoke this skill for prompt changes, not llm-workflow.
- `.claude/agents/prompt-evaluator.md` — sub-agent that runs the eval harness.
- `backend/CLAUDE.md` — backend conventions + gotchas (Anthropic-specific gotchas are here, not duplicated above).
- `CASE_STUDIES.md` — the LLM-adjacent incidents (rate limits, event-loop binding, retry tuning).
