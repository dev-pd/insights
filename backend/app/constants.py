from enum import StrEnum


class FeedbackStatus(StrEnum):
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    SKIPPED = "skipped"
    FAILED = "failed"


class SkipReason(StrEnum):
    """Why a feedback row never reached `extracted` status. See backend/CLAUDE.md
    § LLM module for which rules fire pre-LLM (validator) vs post-LLM (worker)."""

    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    GIBBERISH = "gibberish"
    PROFANITY = "profanity"
    EMPTY = "empty"
    LLM_VALIDATION_ERROR = "llm_validation_error"
    NON_ENGLISH_UNSUPPORTED = "non_english_unsupported"
    PROMPT_INJECTION = "prompt_injection"
    NOISE = "noise"


class LlmCallType(StrEnum):
    EXTRACTION = "extraction"
    SUMMARY = "summary"
