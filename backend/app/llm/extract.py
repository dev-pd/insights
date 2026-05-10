import logging
import time

from pydantic import ValidationError

from app.core.config import get_settings
from app.exceptions import LLMSchemaError
from app.llm.client import call_with_retry, get_client
from app.llm.prompts import ACTIVE_PROMPT, ACTIVE_VERSION
from app.llm.schema import ExtractionResult

log = logging.getLogger(__name__)

TOOL_NAME = "extract_insights"

EXTRACT_TOOL = {
    "name": TOOL_NAME,
    "description": "Return structured insights extracted from customer feedback.",
    "input_schema": ExtractionResult.model_json_schema(),
}


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
