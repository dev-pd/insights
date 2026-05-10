from fastapi import APIRouter

from app.api.deps import SummaryServiceDep
from app.schemas.summary import SummaryOut

router = APIRouter()


@router.get("", response_model=SummaryOut)
async def get_summary(service: SummaryServiceDep) -> SummaryOut:
    """Return the current dashboard summary. Returns cached if present."""
    result = await service.get_summary(force_refresh=False)
    return SummaryOut(**result)


@router.post("/refresh", response_model=SummaryOut)
async def refresh_summary(service: SummaryServiceDep) -> SummaryOut:
    """Force regenerate the summary. Bypasses (and overwrites) the cache."""
    result = await service.get_summary(force_refresh=True)
    return SummaryOut(**result)
