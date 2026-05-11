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
    # English-only for now. Detected at the LLM layer (language field) and
    # mapped here by the worker after extraction. Production graduation:
    # add `langdetect` pre-LLM so we don't burn a call to find out.
    NON_ENGLISH_UNSUPPORTED = "non_english_unsupported"
    # Conservative regex-based detection of obvious prompt-override
    # attempts ("ignore previous instructions", "reveal your prompt").
    # Rejected at the validator so the LLM never sees the payload.
    PROMPT_INJECTION = "prompt_injection"
    # Implausible time framings ("1000 yrs ago", "centuries ago") in
    # product feedback. Caught upstream so the LLM doesn't burn a call
    # producing a debatable sentiment label on inputs that are noise.
    NONSENSICAL_TIMEFRAME = "nonsensical_timeframe"


class LlmCallType(StrEnum):
    """Categories tracked in the llm_usage audit table."""

    EXTRACTION = "extraction"
    SUMMARY = "summary"
