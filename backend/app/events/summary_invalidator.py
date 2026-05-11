"""Background task that debounces feedback_update events and publishes a
`summary_invalidate` notification so the frontend refetches `/v1/summary`.

We deliberately DO NOT delete the cache here — `SummaryService.get_summary`
is fingerprint-aware and skips the LLM call on its own when the EXTRACTED
cohort hasn't changed. Publishing without deleting means a burst that adds
zero new EXTRACTED rows (e.g., all-skipped non-english batch) still wakes
the frontend, /v1/summary serves the cached blob (no LLM cost), and the UI
remains correct.

Started from the FastAPI lifespan (one task per backend process). Receives
events from the worker via `EventChannel.FEEDBACK_UPDATE` on Redis db 0.
"""

import asyncio
import json
import logging

import redis.asyncio as redis_async

from app.events.pubsub import (
    EventChannel,
    publish_summary_invalidation,
)

log = logging.getLogger(__name__)

_TERMINAL_STATUSES = {"extracted", "skipped", "failed"}
_PUBSUB_POLL_SECONDS = 1.0


async def run_summary_invalidator(
    redis_client: redis_async.Redis, debounce_seconds: int
) -> None:
    """Fires at most once per `debounce_seconds` while terminal events keep
    arriving. Two regimes:

    - **During a sustained burst**: the very first event after a quiet period
      starts a `debounce_seconds` timer. When that elapses (regardless of
      whether more events kept arriving), cache is invalidated. This means a
      ~200s ingestion burst produces ~6 summary regens, not zero.
    - **After the burst settles**: the LAST event before quiet still triggers
      one final invalidation `debounce_seconds` later, so the final summary
      reflects the full cohort.

    Tracking state:
    - `first_event_since_last_fire`: timestamp of the first event after the
      most recent invalidation. The debounce timer is anchored here.
    """
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(EventChannel.FEEDBACK_UPDATE.value)
        log.info(
            "summary_invalidator_started",
            extra={"debounce_seconds": debounce_seconds},
        )

        first_event_since_last_fire: float | None = None

        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=_PUBSUB_POLL_SECONDS,
                )
            except asyncio.TimeoutError:
                message = None

            now = asyncio.get_event_loop().time()

            if message and message.get("type") == "message":
                try:
                    data = json.loads(message["data"])
                    status = data.get("status")
                except (json.JSONDecodeError, TypeError):
                    status = None
                if status in _TERMINAL_STATUSES and first_event_since_last_fire is None:
                    first_event_since_last_fire = now

            if (
                first_event_since_last_fire is not None
                and (now - first_event_since_last_fire) >= debounce_seconds
            ):
                try:
                    await publish_summary_invalidation(redis_client)
                    log.info("summary_invalidate_published")
                except Exception as error:  # noqa: BLE001 — invalidator must keep running
                    log.warning(
                        "summary_invalidation_step_failed",
                        extra={"error": str(error)},
                    )
                first_event_since_last_fire = None
    except asyncio.CancelledError:
        log.info("summary_invalidator_cancelled")
        raise
    finally:
        try:
            await pubsub.unsubscribe(EventChannel.FEEDBACK_UPDATE.value)
        except Exception:  # noqa: BLE001 — best-effort teardown
            pass
        await pubsub.close()
