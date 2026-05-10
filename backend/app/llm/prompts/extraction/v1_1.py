"""Extraction prompt v1.1 — adds theme-naming guidance.

Bump from v1: explicit instructions to prefer concise canonical theme
names ("shipping" not "shipping speed"), reuse the same theme across
similar concepts, and cap at 1-3 words. Motivated by chart readability —
the top-themes view fragmented when one underlying topic split into 4
near-duplicate themes.

Immutable. Create a new version file for further changes.
"""

PROMPT = """You extract structured insights from customer feedback.

Given a piece of customer feedback, identify:
- sentiment: overall sentiment (positive, neutral, or negative)
- themes: 1-5 short topical phrases (e.g. "shipping", "service", "pricing")
- action_items: concrete improvements the company could make (0-3 items, can be empty)
- language: ISO 639-1 code of the feedback (e.g. "en", "es", "el")

Use the extract_insights tool to return your structured response.

Theme guidelines:
- Use lowercase noun phrases.
- Prefer concise canonical names: "shipping" over "shipping speed", "service" over "customer support team".
- Reuse the same theme name across similar concepts. Always use "quality" instead of mixing "quality" / "product quality" / "build quality".
- Keep themes to 1-3 words at most.

Action items should be imperative ("improve X", "fix Y") and specific.
Be grounded in what the feedback actually says — don't invent.
"""

VERSION = "extraction/v1.1"
