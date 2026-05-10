---
name: llm-workflow
description: LLM workflow patterns for the feedback extraction backend — tool-use extraction with Pydantic schemas, prompt versioning (immutable past versions, active selector via __init__.py), pre-LLM input validation, async extraction with Celery, the call_llm wrapper (retries/timeout/semaphore/error mapping), cost controls, eval harness with goldens, failure handling, multi-language. Invoke when working in backend/app/llm/.
---

# LLM workflow

Everything LLM-specific in this codebase: how prompts are versioned, how extraction is structured and validated, how we handle failure, how we control cost, and how we evaluate quality. These patterns reflect current AI engineering best practices for production extraction pipelines.

The LLM module lives entirely under `backend/app/llm/`. It has zero knowledge of HTTP or DB schemas; it operates on plain text inputs and Pydantic outputs. This makes it a portable bounded context that lifts cleanly into any host architecture.

## Core extraction approach

We use **tool use as extraction** with Pydantic schema validation. This is the canonical Anthropic pattern for structured output from Claude.

### Why tool use, not freeform JSON

Three reasons we choose tool use over "just ask for JSON":

1. **Schema enforcement at API level.** When the model returns a tool call, Anthropic's API constrains the response to match the tool's `input_schema`. Freeform JSON has no such guarantee.
2. **No parsing gymnastics.** No stripping markdown fences, no fixing trailing commas, no "Here's the JSON:" preambles.
3. **Pydantic round-trip.** We define one Pydantic model, derive the JSON schema for the tool definition, and validate the response back into the same model. One source of truth.

### The pattern

```python
# app/llm/schema.py
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Sentiment = Literal["positive", "neutral", "negative"]


class ExtractionResult(BaseModel):
    """Schema for what we extract from each piece of feedback."""
    
    model_config = ConfigDict(extra="forbid")  # additionalProperties: false in JSON schema

    sentiment: Sentiment = Field(
        description="Overall emotional tone of the feedback."
    )
    themes: list[str] = Field(
        description=(
            "1-3 concise theme labels in lowercase. "
            "Each theme is 1-3 words capturing what the feedback is about. "
            "Examples: 'performance', 'login flow', 'pricing'."
        ),
        min_length=1,
        max_length=3,
    )
    action_items: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete actions the team could take based on this feedback. "
            "Empty list if no clear action implied. "
            "Examples: 'add dark mode', 'investigate slow checkout on mobile'."
        ),
        max_length=5,
    )
    language: str = Field(
        description="ISO 639-1 language code of the input text, e.g. 'en', 'es', 'fr'.",
        min_length=2,
        max_length=2,
    )
```

```python
# app/llm/extract.py
async def extract_insights(
    client: AsyncAnthropic,
    text: str,
    request_id: str,
) -> ExtractionResult:
    schema = ExtractionResult.model_json_schema()
    
    response = await call_llm(
        client,
        request_id,
        model=get_settings().llm_model,
        max_tokens=get_settings().llm_max_tokens,
        system=ACTIVE_PROMPT,
        messages=[{"role": "user", "content": text}],
        tools=[{
            "name": "record_extraction",
            "description": "Record the structured extraction from the feedback.",
            "input_schema": schema,
        }],
        tool_choice={"type": "tool", "name": "record_extraction"},
    )

    tool_input = _extract_tool_input(response)
    return ExtractionResult.model_validate(tool_input)
```

### Rules

- Every extraction goes through Pydantic validation. No raw dict consumption downstream.
- `extra="forbid"` on the Pydantic config so unexpected fields fail loud, not silent.
- `tool_choice={"type": "tool", "name": "..."}` forces the model to call our tool. Without this, Claude may respond conversationally.
- Field descriptions are part of the prompt. Claude reads them. Write them as you would write instructions to a human annotator.

## Prompt versioning

Prompts are first-class artifacts. They live as separate files, never inlined.

### File layout

```
backend/app/llm/prompts/
├── __init__.py     # Exports ACTIVE_PROMPT, ACTIVE_VERSION
├── v1.py           # First version, frozen forever
├── v2.py           # Second version, frozen forever
└── v3.py           # Current version (referenced from __init__.py)
```

### Each version file

```python
# app/llm/prompts/v2.py

PROMPT_VERSION = "v2"

PROMPT_TEXT = """You are extracting structured insights from customer feedback.

For each piece of feedback, identify:

1. SENTIMENT: positive, neutral, or negative
   - positive: clearly favorable or appreciative
   - negative: clearly critical, frustrated, or reporting a problem
   - neutral: balanced, mixed, factual, or unclear

2. THEMES: 1-3 short labels capturing what the feedback is ABOUT
   - Use lowercase, 1-3 words each
   - Be specific: 'login flow' not 'auth', 'mobile checkout' not 'mobile'
   - Avoid generic catch-alls like 'feedback' or 'product'

3. ACTION_ITEMS: concrete actions the team could take
   - Empty list if no clear action implied
   - Concrete and actionable: 'add dark mode' not 'improve UI'
   - Avoid speculation beyond what the feedback supports

4. LANGUAGE: the ISO 639-1 code of the input text

Be precise. Do not invent themes or actions not grounded in the text."""
```

### `__init__.py` selects active

```python
# app/llm/prompts/__init__.py
from app.llm.prompts.v2 import PROMPT_TEXT as ACTIVE_PROMPT
from app.llm.prompts.v2 import PROMPT_VERSION as ACTIVE_VERSION
```

### Rules

- **Never edit a previous version.** Add a new file. Old versions are frozen.
- **The active version is changed by editing `__init__.py` only.** One-line change, easy to revert.
- **Every prompt file exports both `PROMPT_TEXT` and `PROMPT_VERSION`** so traces always know which prompt produced an extraction.
- **Old versions stay in the repo indefinitely.** They are tiny files with huge debugging value.
- **After every active-version change, run the prompt-evaluator subagent** to confirm the new prompt doesn't regress on goldens.

### Why this pattern

- **Reproducibility.** Any past extraction can be re-run with its original prompt by importing from the version file.
- **A/B comparison.** Swap `__init__.py` to point at v3 vs v2, run evals, compare metrics objectively.
- **Audit trail.** Prompt history lives in git. No separate prompt-tracking system needed.
- **Migration safety.** A production deploy can pin a specific version via env var override if needed.

## Pre-LLM input validation

Validation runs BEFORE the LLM call. Saves cost on garbage input and improves UX with clear skip reasons.

### The validator

```python
# app/llm/validate.py
import re
from app.config import get_settings
from app.constants import SkipReason
from better_profanity import profanity


def is_processable(text: str) -> SkipReason | None:
    """Returns None if processable, otherwise the reason to skip."""
    settings = get_settings()
    stripped = text.strip()
    
    if len(stripped) < settings.feedback_min_length:
        return SkipReason.TOO_SHORT
    if len(stripped) > settings.feedback_max_length:
        return SkipReason.TOO_LONG

    alpha_count = sum(1 for c in stripped if c.isalpha() or c.isspace())
    if alpha_count / len(stripped) < settings.feedback_min_alpha_ratio:
        return SkipReason.LOW_ALPHA_RATIO

    if not re.search(r"[a-zA-Z\u00C0-\u024F]{3,}", stripped):
        return SkipReason.NO_WORDS

    if profanity.contains_profanity(stripped):
        return SkipReason.PROFANITY_DETECTED

    return None
```

### Rejection rules (in order)

| Rule | Rejection reason | Why |
|---|---|---|
| Stripped length < 10 chars | `TOO_SHORT` | "ok", "good", or "asdf" carry no extractable signal |
| Stripped length > 5000 chars | `TOO_LONG` | Cost cap; very long text is rarely real feedback, often spam or pasted logs |
| Alpha ratio < 0.4 | `LOW_ALPHA_RATIO` | Mostly punctuation or numbers (`!@#$%^&*` or `1234567890`) |
| No 3+ consecutive letters | `NO_WORDS` | Keyboard mashing like `asdfgh j k l` |
| Profanity detected | `PROFANITY_DETECTED` | Optional content filter; configurable |

### Multi-language consideration

The "3+ consecutive letters" regex includes `\u00C0-\u024F` to cover Latin Extended (Spanish, French, German, etc.). For broader Unicode (Cyrillic, Arabic, CJK), the rule would need to expand. For this PoC the assumption is Latin-script feedback; the validator falls back to TOO_SHORT/LOW_ALPHA for non-Latin garbage.

### Skipped vs failed

- **`status="skipped"`** rows are rejected by the validator. No LLM call. Cheap.
- **`status="failed"`** rows passed the validator but failed during LLM extraction. Always cost an API call.
- Both states are saved with their `skip_reason`. The user sees both in the dashboard. Transparency over silent rejection.

## Async extraction architecture

Submission and extraction are decoupled for responsive UX. Full state machine and timing are in `architecture.md`. The LLM-facing summary:

### Phase 1: synchronous (in-request)

```python
# Inside the POST /feedback handler
for text in payload.texts:
    skip_reason = is_processable(text)
    if skip_reason:
        await save_feedback(session, text, status=FeedbackStatus.SKIPPED, skip_reason=skip_reason)
        continue
    
    feedback = await save_feedback(session, text, status=FeedbackStatus.PROCESSING)
    extract_and_update.delay(feedback.id, request_id)  # Celery dispatch
```

API returns sub-100ms regardless of LLM latency.

### Phase 2: asynchronous (Celery worker)

```python
# app/tasks.py
@celery_app.task(bind=True, max_retries=2)
def extract_and_update(self, feedback_id: str, request_id: str) -> None:
    try:
        asyncio.run(_extract_and_update_async(feedback_id, request_id))
    except LLMRateLimitError as e:
        raise self.retry(exc=e, countdown=60)  # Backoff and retry on rate limit
```

The async helper:
1. Loads the row
2. Calls `extract_insights(text)`
3. Updates the row with result + bumps `updated_at`
4. SSE endpoint picks up the change and pushes to frontend

### Why Celery for a PoC

Defensible at this scale, here is why:

- **Durable.** Worker crash and restart doesn't lose tasks; the broker holds them.
- **Decouples failure modes.** API endpoint stays responsive even if LLM is slow or down.
- **Built-in retry policies** with exponential backoff for transient failures.
- **Horizontal scalability.** Adding workers is config, not code.
- **A `BackgroundTasks` fallback** is documented for environments without Redis. The dispatch boundary is the function `extract_and_update`, identical regardless of dispatcher.

## LLM client patterns

The Anthropic client is wrapped in `app/llm/client.py`. Adds production behavior on top of the raw SDK.

### Wrapper responsibilities

- **Retries** with exponential backoff: 1s, 2s, 4s. Max attempts from Settings. Retries on 429 (rate limit) and 5xx (transient server errors). Does NOT retry on 4xx other than 429 (those are our bug, not transient).
- **Timeout** per call from Settings (default 30s), passed directly to the SDK's native `timeout` parameter on `client.messages.create()`.
- **Bounded concurrency** via module-level `asyncio.Semaphore(N)` where N is from Settings (`llm_concurrency_limit`). Prevents accidentally spawning 100 parallel calls and getting rate-limited.
- **Structured logging** on every call: `prompt_version`, `input_length`, `latency_ms`, `input_tokens`, `output_tokens`, `attempt`, success/failure.
- **Error mapping** from raw Anthropic exceptions to our typed exceptions:
  - `APITimeoutError` → `LLMTimeoutError`
  - 429 status → `LLMRateLimitError`
  - 5xx status → `LLMError`
  - Schema mismatch on Pydantic validation → `LLMValidationError`
- **Metadata propagation.** Every call attaches `request_id` and `prompt_version` to the API request metadata for upstream tracing.

### Pattern

```python
import asyncio
import time
from anthropic import AsyncAnthropic, APIStatusError, APITimeoutError

from app.config import get_settings
from app.exceptions import LLMError, LLMTimeoutError, LLMRateLimitError


_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().llm_concurrency_limit)
    return _semaphore


async def call_llm(client: AsyncAnthropic, request_id: str, **kwargs) -> str:
    settings = get_settings()
    last_error: Exception | None = None

    async with _get_semaphore():
        for attempt in range(settings.llm_max_retries + 1):
            start = time.monotonic()
            try:
                response = await client.messages.create(
                    timeout=settings.llm_timeout_seconds,
                    **kwargs,
                )
                logger.info("llm_call_complete", extra={
                    "latency_ms": int((time.monotonic() - start) * 1000),
                    "attempt": attempt,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "request_id": request_id,
                })
                return response.content[0].text

            except APITimeoutError as e:
                last_error = LLMTimeoutError(str(e))
                logger.warning("llm_call_failed", extra={
                    "event": "llm_call_failed",
                    "error_type": type(e).__name__,
                    "attempt": attempt,
                    "request_id": request_id,
                })
            except APIStatusError as e:
                if e.status_code == 429:
                    last_error = LLMRateLimitError(str(e))
                elif e.status_code >= 500:
                    last_error = LLMError(str(e))
                else:
                    logger.warning("llm_call_failed", extra={
                        "event": "llm_call_failed",
                        "error_type": type(e).__name__,
                        "attempt": attempt,
                        "request_id": request_id,
                    })
                    raise LLMError(str(e)) from e
                logger.warning("llm_call_failed", extra={
                    "event": "llm_call_failed",
                    "error_type": type(e).__name__,
                    "attempt": attempt,
                    "request_id": request_id,
                })

            if attempt < settings.llm_max_retries:
                await asyncio.sleep(2 ** attempt)

    logger.error("llm_call_terminal_failure", extra={
        "event": "llm_call_terminal_failure",
        "error_type": type(last_error).__name__ if last_error else "Unknown",
        "request_id": request_id,
    })
    raise last_error or LLMError("All retries exhausted")
```

## Cost controls

LLM calls cost real money. Patterns we use to keep it bounded:

| Lever | Setting | Rationale |
|---|---|---|
| Model choice | `claude-haiku-4-5` | Fastest and cheapest model that handles this extraction well. ($1/$5 per MTok input/output.) |
| Output token cap | `max_tokens=200` | Extraction output is small JSON; capping prevents runaway. |
| Input length cap | `feedback_max_length=5000` | Validator rejects longer; saves on input tokens. |
| Pre-validation | Validator catches garbage | Roughly 10-20% of real submissions fail validation, all saved API calls. |
| Concurrency limit | `Semaphore(5)` | Bounds parallel cost burst from a batch submission. |
| Retry budget | `max_retries=3` | Exponential backoff so we don't hammer when rate-limited. |

For a production system, additional levers would be: per-user rate limits, daily spend caps, dynamic batching, prompt caching for shared system prompts. Documented in NOTES.md as graduation path; out of scope for this PoC.

## Evaluation harness

The eval harness is the single most important quality lever in this codebase. Without it, prompt changes are guesswork.

### Layout

```
backend/evals/
├── golden.json         # 15-20 hand-labeled feedback examples
└── run_evals.py        # Runner: loads goldens, calls active prompt, reports metrics
```

### Golden file shape

```json
[
  {
    "id": "g001",
    "input": "The app crashes every time I try to upload a photo over 5MB. Frustrating.",
    "expected": {
      "sentiment": "negative",
      "themes": ["upload", "crash", "file size"],
      "action_items": ["fix photo upload crash for large files"],
      "language": "en"
    },
    "edge_case": "Concrete bug report with explicit threshold"
  },
  ...
]
```

### What goldens cover

A good golden set includes:

- **Clear cases of each sentiment** (3-4 of each)
- **Multilingual examples** (1-2 non-English)
- **Edge cases**: very short feedback, very long feedback, mixed sentiment, sarcastic positive ("oh great, another outage")
- **Theme deduplication tests**: feedback that could trigger redundant themes
- **No-action cases**: feedback that's just a feeling, no implied fix
- **Past-tense gotchas**: "the bug WAS fixed yesterday, thanks" should be positive even though it contains "bug"

### Metrics computed

| Metric | How |
|---|---|
| Sentiment exact-match rate | `correct / total` |
| Theme F1 | Set comparison after lowercase + strip. No stemming for the PoC. |
| Action item recall | Exact match on key concept presence, reported as `matched / total`. No fuzzy NLP scoring. |
| Language detection accuracy | Exact match on ISO code |
| Schema validation rate | % of calls that pass Pydantic validation on first try |

### Running evals

```bash
cd backend && uv run python evals/run_evals.py
cd backend && uv run python evals/run_evals.py --json     # Machine-readable, used by subagent
cd backend && uv run python evals/run_evals.py --diff v2  # Compare current active vs v2
```

### When to run

- Before every prompt change is committed.
- Before changing the active version in `prompts/__init__.py`.
- When investigating a regression reported by a real user.
- The `prompt-evaluator` subagent invokes `--json` mode automatically.

### Rules

- **Never edit goldens to make a failing prompt pass.** Goldens are the truth; prompts must conform.
- **Add new goldens when a real-user case reveals a gap.** The set grows over time.
- **Keep the set small enough to run cheaply** (15-20 cases, under $0.10 per full run with Haiku).

## Failure handling

Three categories of failure, three different responses:

### Transient failures (retried)

- Network timeout
- 429 rate limit
- 5xx server error

The wrapped client retries with exponential backoff. The caller doesn't see these unless retries are exhausted.

### Schema validation failures (retried once, then failed)

The model returned a tool call but the input doesn't match our Pydantic schema (rare with `tool_choice` forcing, but possible). Retry the call once with the same input. If it fails again, mark the row as `failed` with `skip_reason="llm_validation_error"`.

This retry happens in `extract.py` at a layer above `call_llm`, since `call_llm` only handles transport-level retries (network, rate limit, 5xx). Schema validation is the caller's responsibility because it depends on the Pydantic model the caller is using.

### Terminal failures (failed)

- Auth errors
- Invalid request (4xx other than 429)
- Retries exhausted on transient failures

Row is marked `failed`. The user sees the failed status with a generic skip_reason; logs have the detail for debugging.

## Multi-language handling

- The model itself is multilingual. We don't need separate prompts per language.
- We extract the language as part of the structured output (ISO 639-1 code).
- The validator accepts non-English input; only the "no 3+ consecutive letters" rule has a Latin bias documented above.
- The frontend displays the language as a small chip on each FeedbackCard, so users can filter or notice patterns.

For a production system with strong non-English requirements: language-specific prompt versions, language-aware validation rules, and per-language eval sets. Out of scope for this PoC.

## What lives elsewhere

- **Custom exception types** (`LLMError`, `LLMTimeoutError`, etc.): `backend/CLAUDE.md` (Custom exceptions section)
- **Layered architecture rules** (api/ → services/ → llm/): `.claude/context/architecture.md`
- **The prompt-evaluator subagent**: `.claude/agents/prompt-evaluator.md`
- **Configuration values** (timeouts, concurrency limits, model name): `app/config.py` Settings

## The signal these patterns send

A senior reviewer reading this LLM module should see:

- Tool use as the canonical extraction pattern, not freeform JSON
- Pydantic as the single source of schema truth (request, response, validation)
- Prompts versioned as immutable artifacts with a clear active selector
- Pre-LLM validation as cost control AND UX feature
- Async extraction with durable queue for responsiveness
- A real eval harness with goldens, not vibes-based prompt tweaking
- Cost controls at every layer (model, tokens, length, concurrency, retries)
- Failure modes mapped to typed exceptions with intentional handling

These are the practices that make an LLM-powered application maintainable past the demo.