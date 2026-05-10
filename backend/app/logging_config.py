import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.config import get_settings


def configure_logging() -> None:
    """Configure root logger to emit structured JSON to stdout.

    Each line carries `timestamp`, `level`, `name`, `message`, plus any
    `extra={...}` fields passed at the call site. Called once at app startup
    via the FastAPI lifespan hook.
    """
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
