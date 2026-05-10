from better_profanity import profanity

from app.constants import SkipReason
from app.core.config import get_settings


def validate_feedback(text: str) -> SkipReason | None:
    """Pre-LLM validation. Returns SkipReason if input should be skipped, None if valid.

    Thresholds (length, alpha ratio) come from Settings — tunable per environment.
    Order matters — cheap checks run first to reject garbage before more expensive
    ones (profanity scan loads a dictionary).
    """
    settings = get_settings()
    stripped = text.strip()

    if not stripped:
        return SkipReason.EMPTY

    if len(stripped) < settings.feedback_min_length:
        return SkipReason.TOO_SHORT

    if len(stripped) > settings.feedback_max_length:
        return SkipReason.TOO_LONG

    alpha_chars = sum(1 for c in stripped if c.isalpha())
    if alpha_chars / len(stripped) < settings.feedback_min_alpha_ratio:
        return SkipReason.GIBBERISH

    if profanity.contains_profanity(stripped):
        return SkipReason.PROFANITY

    return None
