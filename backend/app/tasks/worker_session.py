"""Worker-side async session helpers.

Celery workers are sync; our extraction code is async. The task body uses
`asyncio.run(...)` to bridge — that spins up a fresh event loop per
invocation. SQLAlchemy async engines bind to the loop on first use, so we
build the engine + session factory INSIDE the async body (same loop) and
dispose at the end. Caching the engine module-level would tie it to the
first loop and break subsequent tasks ("Future attached to a different
loop").

The per-task overhead is ~5ms for engine setup vs ~1s for the LLM call —
negligible. A production-scale worker that wanted per-process pooling
would use `worker_process_init` + a long-lived loop, but that's
graduation work.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@asynccontextmanager
async def worker_session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session bound to a fresh engine for the current event loop.

    Always dispose the engine on exit so connections aren't orphaned.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=1,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()
