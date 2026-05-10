from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.repositories.feedback_repository import FeedbackRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_feedback_repository(session: SessionDep) -> FeedbackRepository:
    return FeedbackRepository(session)


FeedbackRepoDep = Annotated[FeedbackRepository, Depends(get_feedback_repository)]


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


RequestIDDep = Annotated[str, Depends(get_request_id)]
