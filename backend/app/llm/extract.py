import asyncio
import logging
import time

from pydantic import ValidationError

from app.core.config import get_settings
from app.exceptions import LLMSchemaError
from app.llm.client import call_with_retry, get_client
from app.llm.prompts.extraction import ACTIVE_PROMPT, ACTIVE_VERSION
from app.llm.schema import ExtractionResult

log = logging.getLogger(__name__)

TOOL_NAME = "extract_insights"

EXTRACT_TOOL = {
    "name": TOOL_NAME,
    "description": "Return structured insights extracted from customer feedback.",
    "input_schema": ExtractionResult.model_json_schema(),
}

# Process-local semaphore bounding concurrent Anthropic calls. Sized from
# Settings.llm_concurrency_limit (default 5).
#
# Why this is only partially effective today:
#   - Celery workers run in PREFORK mode. Each fork is its own OS process
#     with its own event loop, so this semaphore is per-process, not
#     per-container. With celery_worker_concurrency=3, three forks can
#     each hold 3 separate semaphore tokens → up to 3 concurrent calls
#     across the container. The semaphore inside one process is currently
#     a no-op because worker_prefetch_multiplier=1 means each process
#     runs ONE task at a time.
#
# Why we ship it anyway:
#   1. The day we fan out an LLM call inside one task body (e.g.,
#      re-extraction for low-confidence outputs, multi-stage analysis,
#      eval harness running N variants in parallel), this is the right
#      bound and the call site is already correct.
#   2. The FastAPI backend path (summary refresh from request context)
#      DOES run multiple coroutines on a shared loop. If we ever expose
#      a bulk-summary endpoint, this semaphore actually bites.
#   3. Removing it later is risky; adding it now costs nothing.
#
# For real cross-process bounding under Celery, the lever is
# celery_worker_concurrency. A Redis-backed distributed semaphore is the
# production answer — out of scope for this PoC.
_llm_call_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-init so we bind to the right event loop. asyncio.Semaphore
    pre-3.10 was loop-bound on construction; 3.13 is more permissive but
    deferring construction is still the safer pattern across loop changes
    (e.g., asyncio.run per Celery task)."""
    global _llm_call_semaphore
    if _llm_call_semaphore is None:
        settings = get_settings()
        _llm_call_semaphore = asyncio.Semaphore(settings.llm_concurrency_limit)
    return _llm_call_semaphore


async def extract_insights(text: str) -> tuple[ExtractionResult, dict]:
    """Extract insights from feedback text using Anthropic with tool_use forcing.

    Returns (result, metadata) where metadata includes input/output tokens,
    latency, prompt_version, and model id. Raises LLMError subclass on
    transport/schema failures (caller maps to feedback row status).
    """
    settings = get_settings()
    client = get_client()

    async def _call():
        return await client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            system=ACTIVE_PROMPT,
            messages=[{"role": "user", "content": text}],
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )

    start = time.monotonic()
    async with _get_semaphore():
        response = await call_with_retry(_call)
    latency_ms = int((time.monotonic() - start) * 1000)

    # Find the tool_use block matching our forced tool name.
    tool_use_block = None
    for block in response.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            tool_use_block = block
            break

    if tool_use_block is None:
        raise LLMSchemaError(f"No {TOOL_NAME} tool_use in response")

    try:
        result = ExtractionResult.model_validate(tool_use_block.input)
    except ValidationError as e:
        log.warning("llm_schema_validation_failed", extra={"error": str(e)})
        raise LLMSchemaError(f"Tool input failed schema validation: {e}") from e

    metadata = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": latency_ms,
        "prompt_version": ACTIVE_VERSION,
        "model": response.model,
    }

    return result, metadata
