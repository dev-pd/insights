"""Dashboard AI summary generator. Plain-prose output (no tool_use forcing
unlike extract.py) over the `summary/` prompt family. Shares client +
retry wrapper with extract.py."""

import logging
import time
from typing import Any

from app.core.config import get_settings
from app.exceptions import LLMError
from app.llm.client import call_with_retry, get_client
from app.llm.prompts.summary import (
    ACTIVE_PROMPT as ACTIVE_SUMMARY_PROMPT,
    ACTIVE_VERSION as ACTIVE_SUMMARY_VERSION,
)

log = logging.getLogger(__name__)

MAX_FEEDBACK_TEXT_CHARS_IN_PROMPT = 300  # per-item cap; bounds N × text prompt budget


def _format_feedback_for_summary(feedback_items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(feedback_items, start=1):
        sentiment = item.get("sentiment") or "unknown"
        themes = ", ".join(item.get("themes") or [])
        actions = "; ".join(item.get("action_items") or [])
        text = item["text"][:MAX_FEEDBACK_TEXT_CHARS_IN_PROMPT]
        lines.append(
            f"Item {index}: [{sentiment}] {text}\n"
            f"  Themes: {themes or '(none)'}\n"
            f"  Actions: {actions or '(none)'}"
        )
    return "\n\n".join(lines)


async def generate_summary(
    feedback_items: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Returns (summary_text, metadata). When the sample is below
    summary_min_feedback_items, returns a static 'not enough data' string
    with input_tokens=0 (a sentinel SummaryService uses to skip recording
    an llm_usage row for a call that didn't happen)."""
    settings = get_settings()
    min_items = settings.summary_min_feedback_items

    if len(feedback_items) < min_items:
        extracted_count = len(feedback_items)
        if extracted_count == 0:
            placeholder = (
                f"Summary will appear once at least {min_items} feedback items are extracted."
            )
        else:
            placeholder = (
                f"{extracted_count} of {min_items} extracted feedback items ready — "
                f"summary will appear once the threshold is reached."
            )
        return (
            placeholder,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "prompt_version": ACTIVE_SUMMARY_VERSION,
                "model": "n/a",
                "feedback_count": len(feedback_items),
            },
        )

    formatted = _format_feedback_for_summary(feedback_items)
    user_message = (
        f"Here are the {len(feedback_items)} most recent customer feedback items:\n\n"
        f"{formatted}\n\n"
        f"Write the summary now."
    )

    client = get_client()

    async def _call():
        return await client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.summary_max_tokens,
            system=ACTIVE_SUMMARY_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

    start = time.monotonic()
    response = await call_with_retry(_call)
    latency_ms = int((time.monotonic() - start) * 1000)

    summary_text = ""
    for block in response.content:
        if block.type == "text":
            summary_text += block.text
    summary_text = summary_text.strip()

    if not summary_text:
        raise LLMError("Empty summary response from LLM")

    metadata = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": latency_ms,
        "prompt_version": ACTIVE_SUMMARY_VERSION,
        "model": response.model,
        "feedback_count": len(feedback_items),
    }
    log.info(
        "summary_generated",
        extra={
            "feedback_count": len(feedback_items),
            "latency_ms": latency_ms,
            "input_tokens": metadata["input_tokens"],
            "output_tokens": metadata["output_tokens"],
        },
    )
    return summary_text, metadata
