from fastapi import APIRouter

from app.api.v1.routes import feedback, stats

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
v1_router.include_router(stats.router, prefix="/stats", tags=["stats"])
