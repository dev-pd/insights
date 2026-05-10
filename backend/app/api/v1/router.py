from fastapi import APIRouter

from app.api.v1.routes import events, feedback, stats, summary

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
v1_router.include_router(stats.router, prefix="/stats", tags=["stats"])
v1_router.include_router(summary.router, prefix="/summary", tags=["summary"])
# events router exposes /events at the v1 root (not nested under a resource).
v1_router.include_router(events.router, tags=["events"])
