from typing import Annotated

import redis.asyncio as redis_async
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import get_session
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.services.feedback_service import FeedbackService
from app.services.stats_service import StatsService
from app.services.summary_service import SummaryService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_feedback_repository(session: SessionDep) -> FeedbackRepository:
    return FeedbackRepository(session)


FeedbackRepoDep = Annotated[FeedbackRepository, Depends(get_feedback_repository)]


async def get_llm_usage_repository(session: SessionDep) -> LlmUsageRepository:
    return LlmUsageRepository(session)


LlmUsageRepoDep = Annotated[
    LlmUsageRepository, Depends(get_llm_usage_repository)
]


async def get_feedback_service(
    repo: FeedbackRepoDep,
    llm_usage_repo: LlmUsageRepoDep,
) -> FeedbackService:
    return FeedbackService(repo, llm_usage_repo)


FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


async def get_stats_service(
    repo: FeedbackRepoDep,
    llm_usage_repo: LlmUsageRepoDep,
) -> StatsService:
    return StatsService(repo, llm_usage_repo)


StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]


# Module-level singleton: redis-py manages its own pool — per-request init would thrash it.
_redis_client: redis_async.Redis | None = None


async def get_redis() -> redis_async.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis_async.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_max_connections,
            socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        )
    return _redis_client


RedisDep = Annotated[redis_async.Redis, Depends(get_redis)]


async def get_summary_service(
    repo: FeedbackRepoDep,
    llm_usage_repo: LlmUsageRepoDep,
    redis_client: RedisDep,
) -> SummaryService:
    return SummaryService(repo, llm_usage_repo, redis_client)


SummaryServiceDep = Annotated[SummaryService, Depends(get_summary_service)]


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


RequestIDDep = Annotated[str, Depends(get_request_id)]
