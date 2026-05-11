"""Redis pub/sub helpers for SSE event delivery. Fire-and-forget — no
history (disconnected clients miss events and revalidate via SWR). Async
helpers for FastAPI, sync helpers for Celery workers."""

import json
import logging
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import redis as redis_sync
import redis.asyncio as redis_async

log = logging.getLogger(__name__)


class EventChannel(StrEnum):
    FEEDBACK_UPDATE = "events:feedback_update"
    STATS_INVALIDATE = "events:stats_invalidate"
    SUMMARY_INVALIDATE = "events:summary_invalidate"


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


def _summary_invalidation() -> str:
    return json.dumps(
        {
            "kind": "summary_invalidate",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


async def publish_feedback_event(
    redis_client: redis_async.Redis,
    feedback_id: int,
    status: str,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        await redis_client.publish(
            EventChannel.FEEDBACK_UPDATE.value,
            _feedback_event(feedback_id, status, payload),
        )
    except Exception as error:  # noqa: BLE001 — pub/sub failure must not poison the main path
        log.warning(
            "event_publish_failed",
            extra={
                "channel": EventChannel.FEEDBACK_UPDATE.value,
                "feedback_id": feedback_id,
                "error": str(error),
            },
        )


async def publish_stats_invalidation(redis_client: redis_async.Redis) -> None:
    try:
        await redis_client.publish(
            EventChannel.STATS_INVALIDATE.value, _stats_invalidation()
        )
    except Exception as error:  # noqa: BLE001
        log.warning("stats_invalidation_failed", extra={"error": str(error)})


async def publish_summary_invalidation(redis_client: redis_async.Redis) -> None:
    try:
        await redis_client.publish(
            EventChannel.SUMMARY_INVALIDATE.value, _summary_invalidation()
        )
    except Exception as error:  # noqa: BLE001
        log.warning("summary_invalidation_failed", extra={"error": str(error)})


def publish_feedback_event_sync(
    redis_client: redis_sync.Redis,
    feedback_id: int,
    status: str,
    payload: dict[str, Any] | None = None,
) -> None:
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
    try:
        redis_client.publish(EventChannel.STATS_INVALIDATE.value, _stats_invalidation())
    except Exception as error:  # noqa: BLE001
        log.warning("stats_invalidation_failed_sync", extra={"error": str(error)})
