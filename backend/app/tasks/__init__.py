"""Celery task package.

Module path `app.tasks` is what the worker / beat CLIs look for —
`celery -A app.tasks worker` resolves to the `celery_app` instance
exported here.
"""

from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]
