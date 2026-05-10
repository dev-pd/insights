"""Shared async-session factory for Celery worker tasks.

Workers run in sync context but the extraction + summary code is async.
Each task body bridges with `asyncio.run(...)`, and inside the async body
we need a session factory.

A dedicated factory keeps worker session-pool sizing independent of the
FastAPI side: workers run with prefork concurrency (typically 4), so the
pool sizing here is tighter than the request-handling backend's pool.

Module-level singleton so a worker process reuses connections across
tasks; recreating per task would force pool churn for no benefit.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_worker_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=2,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory
