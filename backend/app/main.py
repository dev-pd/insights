import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import router as ops_router
from app.api.v1.router import v1_router
from app.core.config import get_settings
from app.db import Base, engine
from app.exceptions import AppError
from app.core.logging import configure_logging
from app.middleware import (
    RequestIDMiddleware,
    app_error_handler,
    generic_exception_handler,
    sqlalchemy_error_handler,
)

# Side-effect import: SQLAlchemy needs models registered on Base.metadata before create_all.
from app.models import feedback as _feedback  # noqa: F401
from app.models import llm_usage as _llm_usage  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("app_starting", extra={"log_level": settings.log_level})
    # Bootstrap schema on startup. Production graduation = Alembic.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("app_started")
    yield
    logger.info("app_stopping")
    await engine.dispose()
    logger.info("app_stopped")


settings = get_settings()

app = FastAPI(
    title="Feedback Insights API",
    version="0.1.0",
    description="LLM-powered customer feedback extraction and analytics.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(v1_router)
app.include_router(ops_router, tags=["operational"])
