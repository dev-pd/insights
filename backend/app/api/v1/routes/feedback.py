from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import FeedbackServiceDep
from app.schemas.feedback import FeedbackOut

router = APIRouter()


class FeedbackCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_feedback(
    payload: FeedbackCreateRequest,
    service: FeedbackServiceDep,
) -> FeedbackOut:
    feedback = await service.create_feedback(payload.text)
    return FeedbackOut.model_validate(feedback)


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    service: FeedbackServiceDep,
    limit: int = 50,
) -> list[FeedbackOut]:
    items = await service.list_recent(limit=limit)
    return [FeedbackOut.model_validate(item) for item in items]
