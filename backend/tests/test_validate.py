"""Validator tests focused on the nonsensical-timeframe rule.

The rest of the validator (length / alpha-ratio / profanity / injection)
is exercised through the API integration tests; this file covers the
upstream-rejection rule that catches absurd time framings before they
reach the LLM.
"""

import pytest

from app.constants import SkipReason
from app.llm.validate import validate_feedback


@pytest.mark.parametrize(
    "text",
    [
        "product worked 1000 yrs ago and now is bad",
        "service used to be great 500 years ago",
        "this would have been amazing 100 years ago but now feels stale",
        "centuries ago products had real quality and craftsmanship",
        "millennia ago this kind of thing would have been unimaginable",
    ],
)
def test_implausible_timeframes_are_skipped(text: str) -> None:
    assert validate_feedback(text) == SkipReason.NONSENSICAL_TIMEFRAME


@pytest.mark.parametrize(
    "text",
    [
        # Plausible numeric ages (under threshold) — pass through.
        "30 years ago I started programming and this still feels modern",
        "Some products I bought 50 years ago have lasted longer than this one.",
        "99 years ago feels distant but is just within human memory.",
        # No timeframe at all — pass through.
        "The dashboard is slow on Safari iOS — please fix the rendering.",
        # Generic "ago" without a year unit — pass through.
        "I submitted feedback weeks ago and nobody has responded.",
    ],
)
def test_plausible_or_absent_timeframes_pass(text: str) -> None:
    assert validate_feedback(text) != SkipReason.NONSENSICAL_TIMEFRAME
