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
# Loop OBJECT (`is`/`is not`), not `id()`. See get_client() docstring.
_client_loop: asyncio.AbstractEventLoop | None = None


def get_client() -> AsyncAnthropic:
    """Loop-scoped lazy-init Anthropic client. SDK retries disabled
    (`max_retries=0`) — `call_with_retry` owns the loop for structured logs.

    Case Study 7: AsyncAnthropic wraps an httpx pool bound to the creating
    loop. Celery's asyncio.run() builds a fresh loop per task; without
    rebuilding on loop change, the 2nd task per fork hits a closed-loop
    pool → APIError → retry on the live loop succeeds, costing 1s of
    wasted backoff per task.

    Why object identity, not `id()`: CPython recycles addresses across
    GC'd loops. asyncio.run() creates+closes+GCs a loop per task, and the
    next loop very often gets the same address → same id() → the check
    missed every rebuild. A 30-item stress test confirmed: 29/30 tasks
    still emitted the warning under id(). `is` compares the object."""
    global _client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _client is None or _client_loop is not current_loop:
        settings = get_settings()
        _client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=float(settings.llm_timeout_seconds),
            max_retries=0,
        )
        _client_loop = current_loop
    return _client


async def call_with_retry(
    func: Callable[[], Awaitable[T]],
    max_attempts: int | None = None,
    base_delay: float | None = None,
) -> T:
    """Exponential-backoff retry for transient errors only. Retries
    APITimeoutError, RateLimitError (429, longer backoff), and APIError
    with 5xx. Does NOT retry 4xx other than 429 — those are our bug."""
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
            # APIConnectionError lacks status_code — never got a response. Treat as transient.
            status_code = getattr(e, "status_code", None)
            is_transient = status_code is None or (500 <= status_code < 600)
            if is_transient:
                last_error = e
                if attempt == max_attempts - 1:
                    raise LLMError(f"Anthropic transient error: {e}") from e
                delay = base_delay * (2**attempt)
                log.warning(
                    "llm_transient_retry",
                    extra={
                        "attempt": attempt + 1,
                        "delay": delay,
                        "status_code": status_code,
                        "error_type": type(e).__name__,
                    },
                )
                await asyncio.sleep(delay)
            else:
                raise LLMError(str(e)) from e
    raise LLMError(f"Unexpected retry exit: {last_error}")
