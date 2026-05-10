from typing import Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.api.deps import FeedbackServiceDep, SettingsDep
from app.constants import FeedbackStatus
from app.schemas.feedback import FeedbackOut, FeedbackPaginatedResponse

router = APIRouter()


class FeedbackCreateRequest(BaseModel):
    # Outer wall is enforced by Pydantic max_length to reject oversized payloads
    # before the validator. The validator's feedback_max_length (smaller) is the
    # business rule for "we won't process this"; this is the resource-abuse cap.
    text: str = Field(min_length=1)


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_feedback(
    payload: FeedbackCreateRequest,
    service: FeedbackServiceDep,
    settings: SettingsDep,
) -> FeedbackOut:
    if len(payload.text) > settings.feedback_request_max_length:
        # Treat as request-too-large at the API boundary.
        from fastapi import HTTPException

        raise HTTPException(
            status_code=413,
            detail={
                "error": "request_too_large",
                "max_length": settings.feedback_request_max_length,
            },
        )
    feedback = await service.create_feedback(payload.text)
    return FeedbackOut.model_validate(feedback)


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    service: FeedbackServiceDep,
    settings: SettingsDep,
    limit: int | None = Query(default=None, ge=1, le=500),
) -> list[FeedbackOut]:
    """Recent feedback. Used by dashboard widgets and optimistic-update caches."""
    effective_limit = limit if limit is not None else settings.feedback_list_default_limit
    items = await service.list_recent(limit=effective_limit)
    return [FeedbackOut.model_validate(item) for item in items]


@router.get("/paginated", response_model=FeedbackPaginatedResponse)
async def list_feedback_paginated(
    service: FeedbackServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    sentiment: Literal["positive", "neutral", "negative"] | None = Query(default=None),
    q: str | None = Query(
        default=None,
        max_length=200,
        description="Free-text search across feedback text, themes, and action items.",
    ),
) -> FeedbackPaginatedResponse:
    """Paginated feedback for the /feedback table. Total reflects the active filters."""
    items, total = await service.list_paginated(
        offset=offset, limit=limit, sentiment=sentiment, search=q
    )
    return FeedbackPaginatedResponse(
        items=[FeedbackOut.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


class FeedbackBatchRequest(BaseModel):
    # max_length=50 caps batch size for sync processing under Anthropic rate
    # limits and request-timeout budgets. Phase 4 raises this once Celery
    # dispatches each text as its own task.
    texts: list[str] = Field(min_length=1, max_length=50)


class FeedbackBatchResponse(BaseModel):
    items: list[FeedbackOut]
    total: int = Field(description="Total items processed (success + skipped + failed).")
    extracted: int
    skipped: int
    failed: int


@router.post(
    "/batch",
    response_model=FeedbackBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_feedback_batch(
    payload: FeedbackBatchRequest,
    service: FeedbackServiceDep,
) -> FeedbackBatchResponse:
    """Process 1-50 feedback items in one request.

    Sequential processing on the backend — see FeedbackService docstring for the
    rate-limit + session-contention rationale. Per-item failures are isolated.
    """
    results = await service.create_feedback_batch(payload.texts)

    extracted = sum(
        1 for feedback in results if feedback.status == FeedbackStatus.EXTRACTED.value
    )
    skipped = sum(
        1 for feedback in results if feedback.status == FeedbackStatus.SKIPPED.value
    )
    failed = sum(
        1 for feedback in results if feedback.status == FeedbackStatus.FAILED.value
    )

    return FeedbackBatchResponse(
        items=[FeedbackOut.model_validate(feedback) for feedback in results],
        total=len(results),
        extracted=extracted,
        skipped=skipped,
        failed=failed,
    )
