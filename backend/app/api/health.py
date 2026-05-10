import logging

import redis.asyncio as redis_async
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.api.deps import SessionDep
from app.schemas import HealthResponse, ReadyResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness — process is running. Used by docker-compose healthcheck."""
    return HealthResponse(status="ok")


@router.get("/ready")
async def ready(session: SessionDep):
    """Readiness — DB and Redis are reachable. Returns 503 if either is down."""
    settings = get_settings()
    db_ok = False
    redis_ok = False

    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning("ready_db_check_failed", extra={"error": str(e)})

    try:
        r = redis_async.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        redis_ok = True
    except Exception as e:
        logger.warning("ready_redis_check_failed", extra={"error": str(e)})

    if db_ok and redis_ok:
        return ReadyResponse(status="ok", database=True, redis=True)

    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "database": db_ok, "redis": redis_ok},
    )
