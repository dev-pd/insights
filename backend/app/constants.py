from enum import StrEnum


class FeedbackStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class SkipReason(StrEnum):
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    GIBBERISH = "gibberish"
    PROFANITY = "profanity"
    EMPTY = "empty"
    LLM_VALIDATION_ERROR = "llm_validation_error"
