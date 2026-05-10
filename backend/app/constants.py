from enum import StrEnum


class FeedbackStatus(StrEnum):
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    SKIPPED = "skipped"
    FAILED = "failed"


class SkipReason(StrEnum):
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    GIBBERISH = "gibberish"
    PROFANITY = "profanity"
    EMPTY = "empty"
    LLM_VALIDATION_ERROR = "llm_validation_error"


class LlmCallType(StrEnum):
    """Categories tracked in the llm_usage audit table."""

    EXTRACTION = "extraction"
    SUMMARY = "summary"
