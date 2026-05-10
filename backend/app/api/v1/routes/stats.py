from fastapi import APIRouter

from app.api.deps import StatsServiceDep
from app.schemas.stats import StatsOut

router = APIRouter()


@router.get("", response_model=StatsOut)
async def get_stats(service: StatsServiceDep) -> StatsOut:
    """Aggregated stats for the dashboard."""
    return await service.compute_stats()
