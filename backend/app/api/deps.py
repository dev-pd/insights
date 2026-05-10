from typing import Annotated

import redis.asyncio as redis_async
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import get_session
from app.repositories.feedback_repository import FeedbackRepository
from app.services.feedback_service import FeedbackService
from app.services.stats_service import StatsService
from app.services.summary_service import SummaryService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_feedback_repository(session: SessionDep) -> FeedbackRepository:
    return FeedbackRepository(session)


FeedbackRepoDep = Annotated[FeedbackRepository, Depends(get_feedback_repository)]


async def get_feedback_service(repo: FeedbackRepoDep) -> FeedbackService:
    return FeedbackService(repo)


FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


async def get_stats_service(repo: FeedbackRepoDep) -> StatsService:
    return StatsService(repo)


StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]


# Module-level singleton Redis client. redis-py manages its own connection
# pool, so reusing the client across requests is the right shape — creating
# one per request would tear down/recreate the pool every call.
_redis_client: redis_async.Redis | None = None


async def get_redis() -> redis_async.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis_async.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
        )
    return _redis_client


RedisDep = Annotated[redis_async.Redis, Depends(get_redis)]


async def get_summary_service(
    repo: FeedbackRepoDep,
    redis_client: RedisDep,
) -> SummaryService:
    return SummaryService(repo, redis_client)


SummaryServiceDep = Annotated[SummaryService, Depends(get_summary_service)]


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


RequestIDDep = Annotated[str, Depends(get_request_id)]
