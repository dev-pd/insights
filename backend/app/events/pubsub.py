"""Redis pub/sub helpers for SSE event delivery.

Workers PUBLISH events when feedback status changes. The SSE endpoint
SUBSCRIBE's and streams events to connected browsers.

Why pub/sub (not Streams):
  - Fire-and-forget — perfect for "notify connected clients now".
  - No history needed: disconnected clients miss events, then revalidate
    on reconnect via SWR's keepPreviousData + revalidateOnFocus. We
    never need to replay missed events.
  - Streams add consumer groups + ack management for no benefit here.

Why both async + sync helpers:
  - FastAPI / SSE endpoint runs in async context — uses redis.asyncio.
  - Celery worker tasks run in sync context — uses the sync redis client.
  - Publishes are fire-and-forget so the sync path doesn't need to
    await; keeping the two helpers parallel makes the call sites read
    the same on either side.
"""

import json
import logging
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import redis as redis_sync
import redis.asyncio as redis_async

log = logging.getLogger(__name__)


class EventChannel(StrEnum):
    """Redis pub/sub channel names. Strongly typed to avoid string typos
    drifting between publisher and subscriber."""

    FEEDBACK_UPDATE = "events:feedback_update"
    STATS_INVALIDATE = "events:stats_invalidate"


def _feedback_event(
    feedback_id: int, status: str, payload: dict[str, Any] | None
) -> str:
    return json.dumps(
        {
            "feedback_id": feedback_id,
            "status": status,
            "payload": payload or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


def _stats_invalidation() -> str:
    return json.dumps(
        {
            "kind": "stats_invalidate",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


async def publish_feedback_event(
    redis_client: redis_async.Redis,
    feedback_id: int,
    status: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish a per-feedback status change. Async path (FastAPI)."""
    try:
        await redis_client.publish(
            EventChannel.FEEDBACK_UPDATE.value,
            _feedback_event(feedback_id, status, payload),
        )
    except Exception as error:  # noqa: BLE001 — pub/sub failures shouldn't poison the main path
        log.warning(
            "event_publish_failed",
            extra={
                "channel": EventChannel.FEEDBACK_UPDATE.value,
                "feedback_id": feedback_id,
                "error": str(error),
            },
        )


async def publish_stats_invalidation(redis_client: redis_async.Redis) -> None:
    """Tell connected dashboards 'stats changed, please refresh'.

    Cheaper than embedding the new stats in the event — clients just
    refetch /v1/stats which already supports incremental SWR updates.
    """
    try:
        await redis_client.publish(
            EventChannel.STATS_INVALIDATE.value, _stats_invalidation()
        )
    except Exception as error:  # noqa: BLE001
        log.warning(
            "stats_invalidation_failed",
            extra={"error": str(error)},
        )


def publish_feedback_event_sync(
    redis_client: redis_sync.Redis,
    feedback_id: int,
    status: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Sync sibling of publish_feedback_event for Celery worker tasks."""
    try:
        redis_client.publish(
            EventChannel.FEEDBACK_UPDATE.value,
            _feedback_event(feedback_id, status, payload),
        )
    except Exception as error:  # noqa: BLE001
        log.warning(
            "event_publish_failed_sync",
            extra={
                "channel": EventChannel.FEEDBACK_UPDATE.value,
                "feedback_id": feedback_id,
                "error": str(error),
            },
        )


def publish_stats_invalidation_sync(redis_client: redis_sync.Redis) -> None:
    """Sync sibling of publish_stats_invalidation for Celery worker tasks."""
    try:
        redis_client.publish(EventChannel.STATS_INVALIDATE.value, _stats_invalidation())
    except Exception as error:  # noqa: BLE001
        log.warning("stats_invalidation_failed_sync", extra={"error": str(error)})
