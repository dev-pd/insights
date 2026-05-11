"""Dev-grade stress endpoint: dispatches N synthetic feedbacks through the
standard async pipeline. Used by the dashboard button + stress_test.sh.
Pool is drawn from `backend/evals/golden/extraction.jsonl` so every stress
run exercises the same realistic edge-case mix the prompt is hardened
against (sarcasm, multi-issue, technical noise, non-English skip path,
prompt-injection rejection at the validator, etc.). NOT for production —
each item burns a real Anthropic call."""

import json
import logging
import random
from pathlib import Path

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import FeedbackServiceDep, SettingsDep

log = logging.getLogger(__name__)

router = APIRouter()


# Fallback pool used when goldens aren't on disk (e.g., a non-docker dev
# run where the evals/ tree isn't copied alongside the code). 10 hand-
# picked items covering the major sentiment + theme patterns; intentionally
# smaller and less diverse than the real golden pool — when this fallback
# fires, you'll see a less varied stress run, which is a signal to fix the
# deployment (the goldens *should* be available).
_FALLBACK_POOL: tuple[str, ...] = (
    "Product quality is excellent and the shipping was super fast this week.",
    "Mobile app crashes on the login screen on Android 14. Restarting does not help.",
    "Loving the new dashboard! Charts are clear and load quickly.",
    "Pricing tiers are confusing. The pro plan benefits are not clearly explained.",
    "Would absolutely love a dark mode!",
    "Customer support has been unresponsive for over a week.",
    "The UI is gorgeous but checkout is broken and I can't pay.",
    "Had a billing issue last month, support fixed it within an hour.",
    "Realtime collaboration is buttery smooth.",
    "Just make it better. Everything about this product is frustrating right now.",
)

# Resolved at import — read goldens once, not per request.
_GOLDEN_FILE = Path("/app/evals/golden/extraction.jsonl")


def _load_pool() -> tuple[str, ...]:
    if not _GOLDEN_FILE.exists():
        log.warning(
            "stress_test_pool_fallback",
            extra={"reason": "golden_file_missing", "path": str(_GOLDEN_FILE)},
        )
        return _FALLBACK_POOL

    texts: list[str] = []
    try:
        with _GOLDEN_FILE.open() as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    case = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                text = case.get("text")
                if isinstance(text, str) and text:
                    texts.append(text)
    except OSError as error:
        log.warning(
            "stress_test_pool_fallback",
            extra={"reason": "golden_file_unreadable", "error": str(error)},
        )
        return _FALLBACK_POOL

    if not texts:
        log.warning(
            "stress_test_pool_fallback",
            extra={"reason": "golden_file_empty", "path": str(_GOLDEN_FILE)},
        )
        return _FALLBACK_POOL

    return tuple(texts)


_STRESS_POOL: tuple[str, ...] = _load_pool()


class StressTestRequest(BaseModel):
    count: int = Field(default=100, ge=1)


class StressTestResponse(BaseModel):
    dispatched: int
    skipped: int
    failed: int


def _generate_texts(count: int) -> list[str]:
    # Deterministic seed per count → stable mix between runs at the same N,
    # useful for reproducible debugging while still rotating across the pool.
    rng = random.Random(0xC0FFEE + count)
    return [
        f"[stress {index + 1:03d}/{count:03d}] {rng.choice(_STRESS_POOL)}"
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
