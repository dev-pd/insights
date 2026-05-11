"""Dev-grade stress endpoint: dispatches N synthetic feedbacks through the
standard async pipeline. Used by the dashboard button + stress_test.sh.
Server-side templates keep the bundle small and the pool consistent across
call sites. NOT for production — each item burns a real Anthropic call."""

import random

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import FeedbackServiceDep, SettingsDep

router = APIRouter()


# Deterministic seed per count → stable sentiment/theme mix between runs.
_FEEDBACK_TEMPLATES: tuple[str, ...] = (
    "Product quality is excellent and the shipping was super fast this week.",
    "Customer support response time has been disappointing lately. Two days for a reply.",
    "Mobile app crashes on the login screen on Android 14. Restarting does not help.",
    "Pricing tiers are confusing. The pro plan benefits are not clearly explained.",
    "Loving the new dashboard! Charts are clear and load quickly.",
    "Bulk export feature is missing critical fields like sentiment and timestamp.",
    "Onboarding flow had too many steps. Lost interest before finishing setup.",
    "Performance is solid even with 10k records. Filters and search feel instant.",
    "Documentation could use more examples for the API integration endpoints.",
    "Trial expiration warnings were unclear. Account locked without obvious notice.",
    "Theme support is great but I wish dark mode synced with my OS preference.",
    "Search returns irrelevant results when querying short strings. Needs tuning.",
    "Loading spinners feel slow even on small operations. Could use optimistic UI.",
    "Webhook reliability is excellent. Have not seen a missed delivery in months.",
    "Billing UI is buried three levels deep in settings. Hard to find when needed.",
    "Push notifications are landing twice for the same event. Possible duplicate dispatch.",
    "Two-factor auth setup was painless. QR code scanned and worked first try.",
    "CSV import fails silently when a row has trailing commas. No error shown.",
    "Realtime collaboration is buttery smooth. Cursors and selections sync instantly.",
    "Mobile responsive layout breaks on landscape orientation. Side nav overlaps content.",
    "Latency improved dramatically since last week. API calls feel snappier overall.",
    "Email digest is helpful but the unsubscribe link in dark mode is invisible.",
    "Keyboard shortcuts cheat sheet would help power users move faster through the UI.",
    "Date picker defaults to today but the user often wants the same range as last week.",
    "Audio transcription accuracy is impressive even with background noise present.",
)


class StressTestRequest(BaseModel):
    count: int = Field(default=100, ge=1)


class StressTestResponse(BaseModel):
    dispatched: int
    skipped: int
    failed: int


def _generate_texts(count: int) -> list[str]:
    rng = random.Random(0xC0FFEE + count)
    return [
        f"[stress test item {index + 1:03d}/{count:03d}] {rng.choice(_FEEDBACK_TEMPLATES)}"
        for index in range(count)
    ]


@router.post(
    "/stress-test",
    response_model=StressTestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stress_test(
    payload: StressTestRequest,
    service: FeedbackServiceDep,
    settings: SettingsDep,
) -> StressTestResponse:
    count = min(payload.count, settings.stress_test_max_count)
    texts = _generate_texts(count)
    results = await service.create_feedback_batch(texts)

    dispatched = sum(1 for feedback in results if feedback.status == "processing")
    skipped = sum(1 for feedback in results if feedback.status == "skipped")
    failed = sum(1 for feedback in results if feedback.status == "failed")
    return StressTestResponse(dispatched=dispatched, skipped=skipped, failed=failed)
