"""Ad-hoc probe for prompt edge cases.

Runs a small hand-picked set of tricky inputs through the currently-active
extraction prompt and prints raw results — no grading, no thresholds. Use
this BEFORE adding a golden case, to see how the prompt actually behaves
on a candidate input. Once you've decided the expected behavior, the case
can graduate to `golden/extraction.jsonl`.

Usage (from repo root, via docker-compose so backend/.env loads):

    docker compose run --rm \\
      -v "$(pwd)/backend/evals:/app/evals:ro" \\
      backend python /app/evals/explore_edges.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.llm.extract import extract_insights  # noqa: E402
from app.llm.prompts.extraction import ACTIVE_VERSION  # noqa: E402


# (case_id, input_text) — keep these short and obviously-different so the
# trace output stays readable. Don't put expectations here; that's the
# golden file's job.
CASES: list[tuple[str, str]] = [
    (
        "absurd-premise",
        "product worked 1000 yrs ago and now is bad",
    ),
    (
        "pure-praise-no-asks",
        "absolutely love this product, best purchase I've made all year!",
    ),
    (
        "feature-request-enthusiastic",
        "would absolutely love a dark mode!",
    ),
    (
        "resolved-past-tense",
        "had a billing issue last month, support fixed it within an hour",
    ),
    (
        "mixed-with-blocker",
        "the UI is gorgeous but checkout is broken and I can't pay",
    ),
]


async def main() -> None:
    print(f"Probing prompt: {ACTIVE_VERSION}\n")
    for case_id, text in CASES:
        try:
            result, metadata = await extract_insights(text)
        except Exception as error:  # noqa: BLE001 — probe wants raw error surface
            print(f"--- {case_id}")
            print(f"  input:  {text!r}")
            print(f"  ERROR:  {type(error).__name__}: {error}\n")
            continue
        print(f"--- {case_id}")
        print(f"  input:        {text!r}")
        print(f"  sentiment:    {result.sentiment}")
        print(f"  themes:       {result.themes}")
        print(f"  action_items: {result.action_items}")
        print(f"  language:     {result.language}")
        print(f"  model:        {metadata.get('model')}  ({metadata.get('latency_ms')}ms)")
        print()


if __name__ == "__main__":
    asyncio.run(main())
