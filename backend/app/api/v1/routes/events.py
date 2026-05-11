"""SSE endpoint streaming feedback-update + stats-invalidate events from
Redis pub/sub to /api/v1/events. Heartbeat comment every N seconds so idle
connections survive nginx/proxy idle timeouts."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import redis.asyncio as redis_async
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import RedisDep, SettingsDep
from app.events.pubsub import EventChannel

log = logging.getLogger(__name__)

router = APIRouter()

_PUBSUB_POLL_SECONDS = 1.0  # short so loop checks disconnect + heartbeat often


async def _event_stream(
    redis_client: redis_async.Redis,
    request: Request,
    heartbeat_interval_seconds: int,
) -> AsyncIterator[str]:
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(
            EventChannel.FEEDBACK_UPDATE.value,
            EventChannel.STATS_INVALIDATE.value,
        )

        connected_event = {
            "kind": "connected",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        yield f"event: connected\ndata: {json.dumps(connected_event)}\n\n"

        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            if await request.is_disconnected():
                log.info("sse_client_disconnected")
                break

            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=_PUBSUB_POLL_SECONDS,
                )
            except asyncio.TimeoutError:
                message = None

            if message and message["type"] == "message":
                channel = message["channel"]
                data = message["data"]  # str — decode_responses=True on the client
                if channel == EventChannel.FEEDBACK_UPDATE.value:
                    yield f"event: feedback_update\ndata: {data}\n\n"
                elif channel == EventChannel.STATS_INVALIDATE.value:
                    yield f"event: stats_invalidate\ndata: {data}\n\n"

            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= heartbeat_interval_seconds:
                yield ": heartbeat\n\n"  # SSE comment — no client event, keeps proxies alive
                last_heartbeat = now

    finally:
        try:
            await pubsub.unsubscribe(
                EventChannel.FEEDBACK_UPDATE.value,
                EventChannel.STATS_INVALIDATE.value,
            )
        except Exception:  # noqa: BLE001 — best effort during teardown
            pass
        await pubsub.close()
        log.info("sse_pubsub_cleanup_done")


@router.get("/events")
async def stream_events(
    request: Request,
    redis_client: RedisDep,
    settings: SettingsDep,
) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(
            redis_client,
            request,
            heartbeat_interval_seconds=settings.sse_heartbeat_interval_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # belt-and-suspenders for upstreams that buffer
        },
    )
