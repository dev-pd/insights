import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import RedisDep, SessionDep
from app.schemas import HealthResponse, ReadyResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness — process is running. Used by docker-compose healthcheck."""
    return HealthResponse(status="ok")


@router.get("/ready")
async def ready(session: SessionDep, redis_client: RedisDep):
    """Readiness — DB and Redis are reachable. Returns 503 if either is down."""
    db_ok = False
    redis_ok = False

    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except SQLAlchemyError as e:
        logger.warning("ready_db_check_failed", extra={"error": str(e)})

    try:
        await redis_client.ping()
        redis_ok = True
    except RedisError as e:
        logger.warning("ready_redis_check_failed", extra={"error": str(e)})

    if db_ok and redis_ok:
        return ReadyResponse(status="ok", database=True, redis=True)

    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "database": db_ok, "redis": redis_ok},
    )
