import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import AppError, DatabaseError

logger = logging.getLogger(__name__)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status = getattr(exc, "status_code", 500)
    return JSONResponse(
        status_code=status,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error(
        "database_error",
        extra={
            "error_type": type(exc).__name__,
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )
    db_error = DatabaseError(str(exc))
    return await app_error_handler(request, db_error)


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        extra={"request_id": getattr(request.state, "request_id", "unknown")},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )
