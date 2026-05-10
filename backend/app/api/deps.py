from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import get_session
from app.repositories.feedback_repository import FeedbackRepository
from app.services.feedback_service import FeedbackService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_feedback_repository(session: SessionDep) -> FeedbackRepository:
    return FeedbackRepository(session)


FeedbackRepoDep = Annotated[FeedbackRepository, Depends(get_feedback_repository)]


async def get_feedback_service(repo: FeedbackRepoDep) -> FeedbackService:
    return FeedbackService(repo)


FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


RequestIDDep = Annotated[str, Depends(get_request_id)]
