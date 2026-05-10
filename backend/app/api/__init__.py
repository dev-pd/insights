from fastapi import APIRouter

from app.api import health

v1_router = APIRouter(prefix="/v1")

ops_router = APIRouter()
ops_router.include_router(health.router, tags=["operational"])
