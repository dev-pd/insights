from better_profanity import profanity

from app.constants import SkipReason

MIN_LENGTH = 10
MAX_LENGTH = 5000
MIN_ALPHA_RATIO = 0.5


def validate_feedback(text: str) -> SkipReason | None:
    """Pre-LLM validation. Returns SkipReason if input should be skipped, None if valid.

    Order matters — cheap checks run first to reject garbage before more expensive
    ones (profanity scan loads a dictionary).
    """
    stripped = text.strip()

    if not stripped:
        return SkipReason.EMPTY

    if len(stripped) < MIN_LENGTH:
        return SkipReason.TOO_SHORT

    if len(stripped) > MAX_LENGTH:
        return SkipReason.TOO_LONG

    alpha_chars = sum(1 for c in stripped if c.isalpha())
    if alpha_chars / len(stripped) < MIN_ALPHA_RATIO:
        return SkipReason.GIBBERISH

    if profanity.contains_profanity(stripped):
        return SkipReason.PROFANITY

    return None
