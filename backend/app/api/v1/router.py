from fastapi import APIRouter

# Phase 2 will add:
# from app.api.v1.routes import feedback, stats, events

v1_router = APIRouter(prefix="/v1")

# Phase 2 will add:
# v1_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
# v1_router.include_router(stats.router, prefix="/stats", tags=["stats"])
# v1_router.include_router(events.router, prefix="/events", tags=["events"])
