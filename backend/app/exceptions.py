class AppError(Exception):
    """Base for all application exceptions."""


class InputValidationError(AppError):
    """Input failed pre-LLM validation."""


class LLMError(AppError):
    """Base for all LLM-related failures."""


class LLMTimeoutError(LLMError):
    """LLM call exceeded timeout."""


class LLMRateLimitError(LLMError):
    """LLM API rate-limited the request."""


class DatabaseError(AppError):
    """Database operation failed unexpectedly."""


class NotFoundError(AppError):
    """Requested resource was not found."""


EXCEPTION_TO_STATUS: dict[type[AppError], int] = {
    InputValidationError: 400,
    NotFoundError: 404,
    LLMError: 502,
    DatabaseError: 503,
}
