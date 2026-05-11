import re

from better_profanity import profanity

from app.constants import SkipReason
from app.core.config import get_settings


# Conservative regex set for the obvious prompt-injection / override
# patterns. Designed for high precision, not high recall — we accept that
# clever paraphrases get through to the LLM (where temperature=0 + the
# system prompt are the second line of defense). The point is to cheaply
# reject the textbook attempts ("ignore previous instructions",
# "disregard all rules above", "reveal your system prompt") without
# burning a real Anthropic call on them, and to flag them clearly in the
# skipped-rows audit trail.
#
# Bounding the gap with `.{0,40}` keeps the regexes from false-positiving
# on legitimate feedback like "Could you ignore the previous version's
# bug? The instructions in the manual were unclear." — those have too
# much distance between the override verb and the noun.
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

# Threshold above which "<N> years ago" reads as absurd in product
# feedback. 100 keeps the rule conservative — "30 years ago I learned
# to code" or "50 years of computing history" pass, while "1000 yrs
# ago" / "500 years ago" / "100 years ago" are caught.
_NONSENSICAL_AGE_THRESHOLD_YEARS = 100

_NONSENSICAL_NUMERIC_AGE = re.compile(
    r"\b(\d+)\s*(?:yrs?|years?)\s+ago\b",
    re.IGNORECASE,
)

_NONSENSICAL_TIMESCALE_WORDS = re.compile(
    r"\b(?:centuries|millennia|millennium|millenniums)\s+ago\b",
    re.IGNORECASE,
)


def validate_feedback(text: str) -> SkipReason | None:
    """Pre-LLM validation. Returns SkipReason if input should be skipped, None if valid.

    Thresholds (length, alpha ratio) come from Settings — tunable per environment.
    Order matters — cheap checks run first to reject garbage before more expensive
    ones (profanity scan loads a dictionary, regex scans iterate the text)."""
    settings = get_settings()
    stripped = text.strip()

    if not stripped:
        return SkipReason.EMPTY

    if len(stripped) < settings.feedback_min_length:
        return SkipReason.TOO_SHORT

    if len(stripped) > settings.feedback_max_length:
        return SkipReason.TOO_LONG

    alpha_chars = sum(1 for char in stripped if char.isalpha())
    if alpha_chars / len(stripped) < settings.feedback_min_alpha_ratio:
        return SkipReason.GIBBERISH

    if profanity.contains_profanity(stripped):
        return SkipReason.PROFANITY

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(stripped):
            return SkipReason.PROMPT_INJECTION

    age_match = _NONSENSICAL_NUMERIC_AGE.search(stripped)
    if age_match and int(age_match.group(1)) >= _NONSENSICAL_AGE_THRESHOLD_YEARS:
        return SkipReason.NONSENSICAL_TIMEFRAME

    if _NONSENSICAL_TIMESCALE_WORDS.search(stripped):
        return SkipReason.NONSENSICAL_TIMEFRAME

    return None
