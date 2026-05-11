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
# Hold the loop OBJECT, not its id() — see the "Why object identity" note
# below. Keeping a strong ref to one loop at a time is fine; we replace it
# on each loop change so we never accumulate stale references.
_client_loop: asyncio.AbstractEventLoop | None = None


def get_client() -> AsyncAnthropic:
    """Lazy-init module-level Anthropic client, **scoped to the current event loop**.

    SDK retries disabled — we handle retries explicitly for observability.

    Why the loop check (see Case Study 7 in CASE_STUDIES.md):
      AsyncAnthropic wraps an httpx AsyncClient whose connection pool binds
      to the loop it was created in. Celery worker tasks run via
      asyncio.run() — a fresh loop per task. Without this check, the SECOND
      task in a fork would reuse a client whose pool lives on a closed loop
      → first call raises a connection-level APIError → call_with_retry
      catches it, backs off 1s, retries on the live loop → succeeds. The
      symptom is a `llm_transient_retry` WARNING + 1s of wasted backoff on
      every task after the first per fork.

      Rebuilding the client when the loop changes is cheap (no DNS/TLS
      until the first call) and eliminates the wasted retry. The previous
      client is left for GC — its loop is closed so there's nothing to
      explicitly aclose() on it.

      On the FastAPI backend side, there's one long-lived loop, so this
      check is a no-op (the cached loop stays current) and the client is
      reused.

    Why object identity, not id():
      The first version of this fix compared `id(loop)`. id() returns a
      memory-address-based int that CPython reuses when the previous object
      is GC'd. asyncio.run() creates+closes+GCs a loop per task, and the
      next loop very often gets the same address → same id() → the check
      missed every rebuild. The 30-item Haiku stress test caught this:
      29/30 tasks still showed the warning. `is`/`is not` compare the
      Python object directly and aren't fooled by address reuse.
    """
    global _client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from sync context (shouldn't happen — every caller is
        # `async def`). Skip the loop check entirely.
        current_loop = None

    if _client is None or _client_loop is not current_loop:
        settings = get_settings()
        _client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=float(settings.llm_timeout_seconds),
            max_retries=0,
        )
        # Replacing the ref (vs appending) — we hold at most one loop
        # reference at a time, so no accumulation across worker lifetime.
        _client_loop = current_loop
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
            # APIConnectionError (the parent of APITimeoutError) lacks
            # status_code — it never got a response. Treat it as transient
            # and retry, same as a 5xx.
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
