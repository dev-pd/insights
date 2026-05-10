class AppError(Exception):
    """Base for all application exceptions.

    Subclasses set `status_code` as a class attribute. The middleware
    `app_error_handler` reads it via `getattr(exc, "status_code", 500)`.
    """

    status_code: int = 500


class InputValidationError(AppError):
    """Input failed pre-LLM validation."""

    status_code = 400


class LLMError(AppError):
    """Base for all LLM-related failures."""

    status_code = 502


class LLMTimeoutError(LLMError):
    """LLM call exceeded timeout."""


class LLMRateLimitError(LLMError):
    """LLM API rate-limited the request."""

    status_code = 503


class LLMSchemaError(LLMError):
    """LLM tool_use response failed Pydantic schema validation."""


class DatabaseError(AppError):
    """Database operation failed unexpectedly."""

    status_code = 503


class NotFoundError(AppError):
    """Requested resource was not found."""

    status_code = 404
