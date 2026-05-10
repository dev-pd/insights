import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from anthropic import APIError, APITimeoutError, AsyncAnthropic, RateLimitError

from app.core.config import get_settings
from app.exceptions import LLMError, LLMRateLimitError, LLMTimeoutError

log = logging.getLogger(__name__)

T = TypeVar("T")

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Lazy-init module-level Anthropic client. SDK retries disabled —
    we handle retries explicitly for observability."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=float(settings.llm_timeout_seconds),
            max_retries=0,
        )
    return _client


async def call_with_retry(
    func: Callable[[], Awaitable[T]],
    max_attempts: int | None = None,
    base_delay: float | None = None,
) -> T:
    """Retry wrapper with exponential backoff for transient errors.

    `max_attempts` defaults to `settings.llm_max_retries`; `base_delay` to
    `settings.llm_retry_base_delay_seconds`. Both are overridable per call
    so callers (e.g. evals) can tighten or loosen the budget.

    Retries on:
    - APITimeoutError (network)
    - RateLimitError (429) — longer backoff
    - APIError with 5xx status

    Does NOT retry on 4xx errors other than 429 (those are our bug).
    """
    settings = get_settings()
    if max_attempts is None:
        max_attempts = settings.llm_max_retries
    if base_delay is None:
        base_delay = settings.llm_retry_base_delay_seconds

    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await func()
        except APITimeoutError as e:
            last_error = e
            if attempt == max_attempts - 1:
                raise LLMTimeoutError(str(e)) from e
            delay = base_delay * (2**attempt)
            log.warning(
                "llm_timeout_retry",
                extra={"attempt": attempt + 1, "delay": delay},
            )
            await asyncio.sleep(delay)
        except RateLimitError as e:
            last_error = e
            if attempt == max_attempts - 1:
                raise LLMRateLimitError(str(e)) from e
            delay = base_delay * (2**attempt) * 2
            log.warning(
                "llm_rate_limit_retry",
                extra={"attempt": attempt + 1, "delay": delay},
            )
            await asyncio.sleep(delay)
        except APIError as e:
            if e.status_code and 500 <= e.status_code < 600:
                last_error = e
                if attempt == max_attempts - 1:
                    raise LLMError(f"Anthropic server error: {e}") from e
                delay = base_delay * (2**attempt)
                log.warning(
                    "llm_5xx_retry",
                    extra={
                        "attempt": attempt + 1,
                        "delay": delay,
                        "status_code": e.status_code,
                    },
                )
                await asyncio.sleep(delay)
            else:
                raise LLMError(str(e)) from e
    raise LLMError(f"Unexpected retry exit: {last_error}")
