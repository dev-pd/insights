import json
import re

from better_profanity import profanity

from app.constants import SkipReason
from app.core.config import get_settings


def _looks_like_structured_data(stripped: str) -> bool:
    """Detects pasted JSON / serialized objects. The LLM would otherwise
    burn tokens trying to summarize a serialized blob (and usually flag it
    as `is_noise=True` post-LLM anyway — pre-LLM rejection is free)."""
    if len(stripped) < 2:
        return False
    first, last = stripped[0], stripped[-1]
    if (first == "{" and last == "}") or (first == "[" and last == "]"):
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return False
        return isinstance(parsed, (dict, list))
    return False


# High-precision (not high-recall) prompt-injection patterns. The `.{0,40}`
# gap bound is what keeps "could you ignore the previous version's bug?"
# from false-positiving — legitimate uses have too much distance between
# the override verb and the target noun.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:ignore|disregard|forget|override|bypass|skip)\b"
        r"[^.\n]{0,40}\b(?:instruction|prompt|rule|guidance|system|directive)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reveal|show|tell|print|output|expose|display|repeat|leak|dump)\b"
        r"[^.\n]{0,30}\b(?:your|the|all|original|full|system)\b"
        r"[^.\n]{0,30}\b(?:instruction|prompt|rule|guidance|system|directive)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsystem\s+prompt\b",
        re.IGNORECASE,
    ),
)


def validate_feedback(text: str) -> SkipReason | None:
    """Pre-LLM validation. Returns SkipReason if input should be skipped, None
    if it should reach the LLM. Order matters — cheap checks run first."""
    settings = get_settings()
    stripped = text.strip()

    if not stripped:
        return SkipReason.EMPTY

    if len(stripped) < settings.feedback_min_length:
        return SkipReason.TOO_SHORT

    if len(stripped) > settings.feedback_max_length:
        return SkipReason.TOO_LONG

    if _looks_like_structured_data(stripped):
        return SkipReason.STRUCTURED_DATA

    alpha_chars = sum(1 for char in stripped if char.isalpha())
    if alpha_chars / len(stripped) < settings.feedback_min_alpha_ratio:
        return SkipReason.GIBBERISH

    if profanity.contains_profanity(stripped):
        return SkipReason.PROFANITY

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(stripped):
            return SkipReason.PROMPT_INJECTION

    return None
