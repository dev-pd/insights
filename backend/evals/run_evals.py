"""Eval harness for the active extraction prompt.

Runs each golden case through the live extraction pipeline (Anthropic call
via `app.llm.extract.extract_insights`) and scores the result against
hand-labeled expectations.

Usage (from `backend/` directory, with env vars loaded):

    uv run python evals/run_evals.py             # human-readable, no exit code
    uv run python evals/run_evals.py --json      # JSON to stdout
    uv run python evals/run_evals.py --check     # exit 1 if metrics regress
    uv run python evals/run_evals.py --limit 5   # only first 5 cases (fast dev)

Exit codes:
  0  all metrics ≥ baseline thresholds (or --check not used)
  1  one or more metrics regressed below threshold
  2  harness / IO error (bad file, network failure, etc.)

Cost: ~30 input tokens × N goldens + ~1 LLM call/case. At N=15 with Haiku
that's roughly $0.005 per run. With Opus, ~$0.30. Always run with the
production model you intend to ship the prompt for — different models
produce different results and the same prompt can pass on Opus, fail on
Haiku, or vice versa.

Configuration:
  ANTHROPIC_API_KEY must be set (read from backend/.env locally, from
  GitHub Actions secrets in CI).
  LLM_MODEL controls which model the eval scores against.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN_PATH = REPO_ROOT / "evals" / "golden" / "extraction.jsonl"
DEFAULT_BASELINE_PATH = REPO_ROOT / "evals" / "baseline.json"

# Ensure `import app...` works whether we're invoked from repo root or backend/.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.exceptions import LLMError  # noqa: E402
from app.llm.extract import extract_insights  # noqa: E402
from app.llm.prompts.extraction import ACTIVE_VERSION  # noqa: E402


def _load_goldens(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open() as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"{path}:{line_no}: invalid JSON ({error})"
                ) from error
    return cases


def _theme_subset_match(
    expected_subset: Iterable[str], actual_themes: Iterable[str]
) -> bool:
    """Each expected term must appear as a substring in at least one actual
    theme (case-insensitive). Lenient because the LLM paraphrases — "shipping"
    in the expectation matches "shipping speed" in the actual."""
    actuals_lower = [theme.lower() for theme in actual_themes]
    return all(
        any(expected.lower() in actual for actual in actuals_lower)
        for expected in expected_subset
    )


async def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    text: str = case["text"]
    try:
        result, metadata = await extract_insights(text)
    except LLMError as error:
        return {
            "id": case["id"],
            "all_pass": False,
            "error": {"type": type(error).__name__, "message": str(error)},
            "checks": {},
        }

    checks: dict[str, dict[str, Any]] = {}

    # is_noise check — runs FIRST. The model flags absurd / nonsense input
    # via the is_noise schema field; the worker skips such rows downstream
    # so the dashboard doesn't count them. When the golden expects noise,
    # ONLY the is_noise check runs — the other field outputs are populated
    # but downstream-ignored, so grading them adds noise to the metrics.
    expected_is_noise: bool = case.get("expected_is_noise", False)
    checks["is_noise"] = {
        "expected": expected_is_noise,
        "actual": result.is_noise,
        "pass": result.is_noise == expected_is_noise,
    }
    if expected_is_noise:
        return {
            "id": case["id"],
            "all_pass": checks["is_noise"]["pass"],
            "checks": checks,
            "model": metadata.get("model"),
            "latency_ms": metadata.get("latency_ms"),
            "input_tokens": metadata.get("input_tokens"),
            "output_tokens": metadata.get("output_tokens"),
        }

    # Sentiment — exact match.
    expected_sentiment = case["expected_sentiment"]
    checks["sentiment"] = {
        "expected": expected_sentiment,
        "actual": result.sentiment,
        "pass": result.sentiment == expected_sentiment,
    }

    # Themes subset — every expected term appears as substring in at least one
    # returned theme. Cases with empty expected_themes_subset skip this check.
    expected_subset: list[str] = case.get("expected_themes_subset", [])
    if expected_subset:
        checks["themes_subset"] = {
            "expected_subset": expected_subset,
            "actual_themes": list(result.themes),
            "pass": _theme_subset_match(expected_subset, result.themes),
        }
    else:
        checks["themes_subset"] = {
            "skipped": True,
            "actual_themes": list(result.themes),
        }

    # Theme count — upper bound (prompt allows 1-5; some cases want a tighter
    # cap). Hitting it likely means the model is over-extracting.
    max_count: int = case.get("expected_themes_max_count", 5)
    checks["themes_count"] = {
        "max": max_count,
        "actual": len(result.themes),
        "pass": len(result.themes) <= max_count,
    }

    # Action items: two checks rolled into one slot.
    #   1) Presence/absence — required by the case or not? Match exact text
    #      is too brittle (model paraphrases every time), so only presence.
    #      Pass `null` (or omit) to skip the presence check entirely — useful
    #      for borderline cases where either empty or non-empty is defensible.
    #   2) Optional forbidden-substring check — if the case declares
    #      `expected_action_items_forbidden_substrings`, fail if any action
    #      item contains any of those substrings (case-insensitive). Used to
    #      catch content-level bugs like an action item parroting an absurd
    #      premise from the input ("match historical standards from 1000
    #      years ago"). Presence checks alone miss this.
    expected_required: bool | None = case.get("expected_action_items_required")
    actual_has = len(result.action_items) > 0
    presence_pass = True if expected_required is None else expected_required == actual_has
    forbidden: list[str] = case.get(
        "expected_action_items_forbidden_substrings", []
    )
    forbidden_hit: tuple[str, str] | None = None
    if forbidden:
        for item in result.action_items:
            item_lower = item.lower()
            for substring in forbidden:
                if substring.lower() in item_lower:
                    forbidden_hit = (item, substring)
                    break
            if forbidden_hit:
                break
    checks["action_items"] = {
        "expected_required": expected_required,
        "actual_count": len(result.action_items),
        "actual_items": list(result.action_items),
        "forbidden_substrings": forbidden,
        "forbidden_hit": (
            {"action_item": forbidden_hit[0], "substring": forbidden_hit[1]}
            if forbidden_hit
            else None
        ),
        "pass": presence_pass and forbidden_hit is None,
    }

    # Language — exact ISO 639-1 match.
    checks["language"] = {
        "expected": case["expected_language"],
        "actual": result.language,
        "pass": result.language == case["expected_language"],
    }

    # all_pass: every non-skipped check passed.
    all_pass = all(check.get("pass", True) for check in checks.values())

    return {
        "id": case["id"],
        "all_pass": all_pass,
        "checks": checks,
        "model": metadata.get("model"),
        "latency_ms": metadata.get("latency_ms"),
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
    }


def _aggregate(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(case_results)
    if total == 0:
        return {"overall_pass_rate": 0.0}

    def _rate(numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 3)

    # Per-field denominators count only cases that ran that check. Noise
    # cases short-circuit after is_noise (the other fields aren't used
    # downstream) so they shouldn't drag per-field rates down.
    def _count(field: str) -> tuple[int, int]:
        cases = [r for r in case_results if field in r["checks"]]
        return (
            sum(1 for r in cases if r["checks"][field].get("pass")),
            len(cases),
        )

    sentiment_pass, sentiment_total = _count("sentiment")
    theme_count_pass, theme_count_total = _count("themes_count")
    action_items_pass, action_items_total = _count("action_items")
    language_pass, language_total = _count("language")
    is_noise_pass, is_noise_total = _count("is_noise")
    overall_pass = sum(1 for r in case_results if r["all_pass"])

    # Theme subset only over cases that have non-empty expected_themes_subset.
    # Excludes LLMError cases (which carry an empty `checks: {}` so any per-key
    # access would KeyError) — they're counted as overall failures but skipped
    # in the per-metric rates, mirroring the .get() pattern used above.
    subset_cases = [
        r for r in case_results
        if "themes_subset" in r["checks"]
        and not r["checks"]["themes_subset"].get("skipped")
    ]
    subset_pass = sum(1 for r in subset_cases if r["checks"]["themes_subset"]["pass"])

    return {
        "sentiment_accuracy": _rate(sentiment_pass, sentiment_total),
        "theme_subset_pass_rate": (
            _rate(subset_pass, len(subset_cases))
            if subset_cases
            else None
        ),
        "theme_count_pass_rate": _rate(theme_count_pass, theme_count_total),
        "action_items_pass_rate": _rate(action_items_pass, action_items_total),
        "language_accuracy": _rate(language_pass, language_total),
        "is_noise_accuracy": _rate(is_noise_pass, is_noise_total),
        "overall_pass_rate": _rate(overall_pass, total),
    }


async def _run_all(goldens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Sequential — the eval is small (~15 cases) and concurrent calls would
    # bunch up against Anthropic's RPM cap. ~30s wall clock total at Haiku
    # latency.
    results: list[dict[str, Any]] = []
    for case in goldens:
        results.append(await _evaluate_case(case))
    return results


def _print_human_readable(report: dict[str, Any]) -> None:
    print(f"Eval report — {report['prompt_version']} on {report.get('model') or '(no model)'}")
    print(f"  cases:    {report['n_cases']}")
    print(f"  elapsed:  {report['elapsed_seconds']}s")
    print()
    print("  metrics:")
    for metric, value in report["metrics"].items():
        if value is None:
            print(f"    {metric}: n/a")
        else:
            print(f"    {metric}: {value:.1%}" if isinstance(value, float) else f"    {metric}: {value}")
    failed = [c for c in report["cases"] if not c["all_pass"]]
    if failed:
        print()
        print(f"  {len(failed)} failed case(s):")
        for c in failed:
            failing_checks = [
                k for k, v in c["checks"].items()
                if isinstance(v, dict) and v.get("pass") is False
            ]
            print(f"    - {c['id']}: {', '.join(failing_checks) or '(error)'}")
            for k in failing_checks:
                check = c["checks"][k]
                expected = check.get("expected") or check.get("expected_subset") or check.get("expected_required")
                actual = check.get("actual") or check.get("actual_themes") or check.get("actual_count")
                print(f"        {k}: expected={expected!r} actual={actual!r}")
                # Surface forbidden-substring hits inline — without this, the
                # caller has to read the JSON to see WHY action_items failed
                # when presence was fine but content was wrong.
                if k == "action_items" and check.get("forbidden_hit"):
                    hit = check["forbidden_hit"]
                    print(
                        f"        action_items forbidden-substring hit: "
                        f"item={hit['action_item']!r} matched={hit['substring']!r}"
                    )


def _check_against_baseline(
    report: dict[str, Any], baseline_path: Path
) -> int:
    if not baseline_path.exists():
        print(
            f"WARN: baseline missing at {baseline_path}; skipping --check gate",
            file=sys.stderr,
        )
        return 0
    with baseline_path.open() as fh:
        baseline = json.load(fh)
    thresholds: dict[str, float] = baseline.get("thresholds", {})
    regressions: list[tuple[str, float, float]] = []
    for metric, threshold in thresholds.items():
        actual = report["metrics"].get(metric)
        if actual is None:
            continue
        if actual < threshold:
            regressions.append((metric, actual, threshold))
    if regressions:
        print("\n  REGRESSIONS vs baseline thresholds:", file=sys.stderr)
        for metric, actual, threshold in regressions:
            print(f"    - {metric}: {actual} < {threshold}", file=sys.stderr)
        return 1
    print("\n  all metrics ≥ baseline thresholds", file=sys.stderr)
    return 0


def _resolve_report_path(report_path: Path, prompt_version: str) -> Path:
    """If the filename component is `AUTO`, substitute it with a stable
    timestamped name `<UTC-ISO>-<prompt-version>.json` so reports from
    multiple runs don't collide and the filename encodes which prompt
    version was tested. Any other path is used as-is."""
    if report_path.name == "AUTO":
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_version = prompt_version.replace("/", "-")
        return report_path.parent / f"{timestamp}-{safe_version}.json"
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any metric is below the baseline threshold.",
    )
    parser.add_argument("--baseline-path", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--golden-path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N cases. Useful for fast dev iteration.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help=(
            "If set, also write the JSON report to this path. If the filename "
            "is literally `AUTO`, substitute with `<UTC-ISO>-<prompt-version>.json` "
            "in the same directory (e.g., `evals/reports/AUTO`). Parent dirs are "
            "created if missing. Independent of --json (which controls stdout)."
        ),
    )
    args = parser.parse_args()

    if not args.golden_path.exists():
        print(f"ERROR: golden set not found at {args.golden_path}", file=sys.stderr)
        return 2

    goldens = _load_goldens(args.golden_path)
    if args.limit is not None:
        goldens = goldens[: args.limit]
    if not goldens:
        print("ERROR: no golden cases to run", file=sys.stderr)
        return 2

    settings = get_settings()
    started = time.monotonic()
    case_results = asyncio.run(_run_all(goldens))
    elapsed = time.monotonic() - started

    report = {
        "prompt_version": ACTIVE_VERSION,
        "model": settings.llm_model,
        "n_cases": len(case_results),
        "elapsed_seconds": round(elapsed, 1),
        "metrics": _aggregate(case_results),
        "cases": case_results,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human_readable(report)

    if args.report_path is not None:
        resolved = _resolve_report_path(args.report_path, ACTIVE_VERSION)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("w") as fh:
            json.dump(report, fh, indent=2)
        print(f"\n  report saved → {resolved}", file=sys.stderr)

    if args.check:
        return _check_against_baseline(report, args.baseline_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
