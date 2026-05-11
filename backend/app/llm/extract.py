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

# Per-process semaphore. No-op under prefork Celery (one task per fork via
# prefetch_multiplier=1) but bites the FastAPI summary path and any future
# intra-task fan-out. Cross-process bounding lives in celery_worker_concurrency.
_llm_call_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    # Lazy-init so construction binds to the live loop, not the import-time loop.
    global _llm_call_semaphore
    if _llm_call_semaphore is None:
        settings = get_settings()
        _llm_call_semaphore = asyncio.Semaphore(settings.llm_concurrency_limit)
    return _llm_call_semaphore


async def extract_insights(text: str) -> tuple[ExtractionResult, dict]:
    """Returns (result, metadata). Metadata includes tokens, latency,
    prompt_version, model id. Raises LLMError subclass on transport/schema
    failures."""
    settings = get_settings()
    client = get_client()

    async def _call():
        return await client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            # temperature=0: borderline cases (e.g. "would absolutely love a dark
            # mode!" on the neutral/positive boundary) flipped run-to-run at temp=1.0
            # even with explicit sentiment rules. The summary prompt uses default temp
            # since prose benefits from variability.
            temperature=0,
            system=ACTIVE_PROMPT,
            messages=[{"role": "user", "content": text}],
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )

    start = time.monotonic()
    async with _get_semaphore():
        response = await call_with_retry(_call)
    latency_ms = int((time.monotonic() - start) * 1000)

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
