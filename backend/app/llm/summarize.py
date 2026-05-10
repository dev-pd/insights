"""LLM-based summarization of recent feedback for the dashboard widget.

Distinct from `extract.py`:
  - Different concern (aggregate analysis, not per-item extraction).
  - Different versioning (`summary/v1` family, see `prompts/summary/`).
  - No tool_use forcing — we want plain prose, not a JSON schema.

Reuses the same Anthropic client + retry wrapper as extraction so timeout,
rate-limit, and 5xx behaviour stay consistent across LLM workflows.
"""

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

# How much of each item's raw text we feed into the prompt. Truncates to
# keep total prompt size bounded when N items × M chars otherwise blows
# the budget. Tied to prompt design, not env-tunable.
MAX_FEEDBACK_TEXT_CHARS_IN_PROMPT = 300


def _format_feedback_for_summary(feedback_items: list[dict[str, Any]]) -> str:
    """Render the items as a numbered block the model can scan.

    Keys we expect on each item: text, sentiment, themes, action_items.
    """
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
    """Generate a 2-3 sentence summary of recent feedback.

    Returns (summary_text, metadata). Metadata mirrors the extract.py shape:
    input/output tokens, latency, prompt_version, model, plus feedback_count.

    When fewer than `summary_min_feedback_items` items are provided, returns
    a static "not enough data" message rather than asking the model to
    summarize a thin sample.

    Raises LLMError (or a subclass) on transport / empty-response failures —
    the caller decides whether to cache or surface the failure.
    """
    settings = get_settings()
    min_items = settings.summary_min_feedback_items

    if len(feedback_items) < min_items:
        return (
            "Not enough feedback yet to generate a meaningful summary. "
            f"Add at least {min_items} feedback items to see insights here.",
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
