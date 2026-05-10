# Backend conventions

How to write Python code in this project. Applies to everything under `backend/`. These are non-negotiable conventions: when generating or editing backend code, follow them without exception.

## Python version and tooling

- Python 3.11 minimum. Use modern syntax: `str | None` instead of `Optional[str]`, `list[str]` instead of `List[str]`.
- Package management via `uv`. Never `pip install` directly; always `uv add` or edit `pyproject.toml`.
- Run scripts with `uv run`. Run tests with `uv run pytest`.

## Naming

| Element | Convention | Example |
|---|---|---|
| Module file | snake_case | `feedback_service.py` |
| Function | snake_case | `extract_insights`, `is_processable` |
| Async function | snake_case (no `async_` prefix) | `process_batch` not `async_process_batch` |
| Class | PascalCase | `Feedback`, `ExtractionResult` |
| Constant | UPPER_SNAKE_CASE | `LLM_TIMEOUT_SECONDS`, `MAX_RETRY_ATTEMPTS` |
| Private function/var | leading underscore | `_save_pending`, `_LLM_SEMAPHORE` |
| Type alias | PascalCase | `FeedbackId = uuid.UUID` |
| Enum class | PascalCase | `FeedbackStatus` |
| Enum member | UPPER_SNAKE_CASE | `FeedbackStatus.PROCESSING` |

## Type hints

Required on every function signature (parameters and return type). No exceptions.

```python
# Good
async def extract_insights(text: str, request_id: str) -> ExtractionResult:
    ...

# Bad - missing return type
async def extract_insights(text: str, request_id: str):
    ...

# Bad - missing parameter types
async def extract_insights(text, request_id):
    ...
```

Use modern union syntax (`X | None`) and built-in generics (`list[X]`, `dict[X, Y]`) instead of `typing.Optional` or `typing.List`.

For FastAPI dependency injection and Pydantic field constraints, use `Annotated`:

```python
from typing import Annotated
from fastapi import Depends, Query

async def search_feedback(
    q: Annotated[str | None, Query(max_length=200)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> FeedbackListResponse:
    ...
```

## Pydantic

All API request and response shapes are Pydantic models. Defined in `app/schemas.py`. Never accept or return raw `dict` from an API endpoint.

```python
# Good
class FeedbackBatchIn(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=100)

@router.post("/feedback")
async def create_feedback(payload: FeedbackBatchIn) -> FeedbackBatchOut:
    ...

# Bad - raw dict in/out
@router.post("/feedback")
async def create_feedback(payload: dict) -> dict:
    ...
```

LLM output is validated through Pydantic in `app/llm/schema.py`. Configuration is validated through Pydantic Settings in `app/config.py`.

Use `Field(..., description="...")` for non-obvious fields. The description shows up in generated OpenAPI docs.

## No magic values

If a value could vary, repeat, or change with environment, it does NOT live inline in code.

| Type of value | Where it lives |
|---|---|
| Numeric thresholds (timeouts, retry counts, batch sizes) | `app/config.py` Settings |
| Status strings, skip reasons, enum-like strings | `app/constants.py` as `StrEnum` classes |
| HTTP status codes | `fastapi.status.HTTP_*` constants |
| Database connection strings, API keys | `app/config.py` Settings (loaded from env) |
| Repeated string literals | Module-level constants with descriptive names |

```python
# Good
from app.config import get_settings
from app.constants import FeedbackStatus
from fastapi import status

settings = get_settings()
if elapsed > settings.llm_timeout_seconds:
    raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, ...)
feedback.status = FeedbackStatus.PROCESSING

# Bad
if elapsed > 30:
    raise HTTPException(status_code=504, ...)
feedback.status = "processing"
```

Rule of thumb: if a string or number appears in two or more files, extract it to a constant.

## Async patterns

Every endpoint is `async`. Every database call goes through the async SQLAlchemy session. Every LLM call goes through the async wrapped client.

### asyncio.gather for parallel work

```python
import asyncio

# Good - parallel with bounded concurrency
async def process_batch(texts: list[str]) -> list[FeedbackOut]:
    semaphore = asyncio.Semaphore(5)
    
    async def process_with_limit(text: str) -> FeedbackOut:
        async with semaphore:
            return await process_one(text)
    
    results = await asyncio.gather(
        *[process_with_limit(text) for text in texts],
        return_exceptions=True,
    )
    return [r for r in results if not isinstance(r, Exception)]

# Bad - sequential, no concurrency
async def process_batch(texts: list[str]) -> list[FeedbackOut]:
    results = []
    for text in texts:
        results.append(await process_one(text))
    return results
```

### return_exceptions=True for fault isolation

When using `asyncio.gather` for batch work, always set `return_exceptions=True` so one failure does not abort the entire batch. Then handle exceptions per-item.

### Bounded concurrency

When calling external services (LLM API, third-party HTTP), use `asyncio.Semaphore` to bound parallel calls. The limit lives in `config.py` as a Setting.

## Imports

Order: standard library → third-party → local app modules. Within each group, alphabetical. Use absolute imports always.

```python
# Good
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Feedback, get_session
from app.llm.extract import extract_insights
from app.schemas import FeedbackBatchIn, FeedbackBatchOut

# Bad - wildcard import
from fastapi import *

# Bad - relative import
from ..llm.extract import extract_insights
```

No wildcard imports. No relative imports.

## Error messages

Two audiences for error messages: the user (via API response) and the operator (via logs). They have different needs.

### User-facing (API response detail)

- Short, actionable, no jargon.
- Never expose internal details (stack traces, SQL, internal paths).
- Use the structured error response shape: `{ error, detail, request_id }`.

```python
# Good
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={"error": "input_too_long", "field": "text", "max_length": 5000},
)

# Bad - exposes internals
raise HTTPException(
    status_code=400,
    detail=f"InputValidator.check_length failed at line 42: {repr(text)[:200]}",
)
```

### Logs (for operators)

- Structured with context: include `request_id`, `feedback_id`, relevant input characteristics.
- Use `logger.exception()` to capture full traceback on caught exceptions.
- Use `logger.warning()` for handled-but-noteworthy issues.
- See `production-patterns.md` for the full logging contract.

## Custom exceptions

Defined in `app/exceptions.py`. Each layer raises specific exception types so callers can handle them precisely.

```python
class AppError(Exception):
    """Base for all application exceptions."""

class InputValidationError(AppError):
    """Input failed pre-LLM validation."""

class LLMError(AppError):
    """Base for all LLM-related failures."""

class LLMTimeoutError(LLMError):
    """LLM call exceeded timeout."""

class LLMValidationError(LLMError):
    """LLM returned output that failed schema validation after retries."""

class LLMRateLimitError(LLMError):
    """LLM API rate-limited the request."""

class DatabaseError(AppError):
    """Database operation failed unexpectedly."""
```

Catch what you can handle. Re-raise what you can't. Never bare `except:`. Never `except Exception` without a clear reason.

```python
# Good
try:
    extraction = await extract_insights(text)
except LLMTimeoutError:
    logger.warning("llm_timeout", extra={"feedback_id": feedback_id})
    return await mark_failed(feedback_id, reason="llm_timeout")
except LLMError as e:
    logger.exception("llm_terminal_error", extra={"feedback_id": feedback_id})
    return await mark_failed(feedback_id, reason="llm_error")

# Bad - swallows all exceptions silently
try:
    extraction = await extract_insights(text)
except:
    pass
```

## Functions and modules

### Function size

Keep functions focused. If a function is over 40 lines, consider whether it should be split. Long functions usually combine multiple concerns.

### Single responsibility

Each module has one primary concern. `extract.py` does extraction. `validate.py` does validation. Don't put validation helpers in `extract.py` because they're used during extraction.

### Pure functions where possible

Functions that don't touch DB or external services should be pure (same inputs always produce same outputs). Validators are a great example: `is_processable(text)` returns the same answer every time for the same text. This makes testing trivial.

## Comments

Code should be self-documenting through good naming. Comments only when WHY isn't obvious from the code.

```python
# Good - explains a non-obvious choice
# We use isalpha() for unicode-aware letter matching, since
# user feedback can be in any language.
alpha_count = sum(1 for c in text if c.isalpha() or c.isspace())

# Bad - restates the code
# Loop through each character in the text
for c in text:
    ...
```

No commented-out code in commits. Either delete it or commit it.

## Testing

See `production-patterns.md` for testing conventions. Quick rules:

- Every validator rejection rule has a test.
- Every service function has a happy path + at least one error path test.
- LLM calls are always mocked in tests; no real API calls in test runs.
- Use `pytest-asyncio` for async tests.
- Fixtures live in `conftest.py`.

## Style

Use `ruff` for linting and formatting. Configuration in `pyproject.toml`. Standard rules; no exotic enforcement.

Line length: 100 characters. Longer is fine for strings and URLs that don't break naturally.

No premature optimization. Write the clear version first. Profile before optimizing. Document any non-obvious optimization.