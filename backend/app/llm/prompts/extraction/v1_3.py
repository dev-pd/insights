"""Extraction prompt v1.3 — tighten theme count to spec (1-3).

The take-home spec says "1-3 themes" per feedback. v1.1 and v1.2 both
asked for "1-5 short topical phrases" — a holdover from earlier
iteration when over-extraction wasn't a concern. The schema was even
more permissive (`max_length=8`). v1.3 brings both prompt and schema
in line with the spec.

Spec compliance aside, the tighter cap pays off in the aggregate top-
themes chart: fewer near-synonym themes per item means cleaner counts.
The canonicalization rules from v1.2 (which collapse "customer service"
/ "service team" / "responsiveness" → "support" etc.) keep working;
this change just forbids a third option of "all of the above" by
listing every synonym separately.

Only the theme-count line changes from v1.2. Sentiment guidelines, theme
canonicalization rules, the fictional-framing rule, and action item
grounding all carry over verbatim.

Immutable. Create a new version file for further changes.
"""

PROMPT = """You extract structured insights from customer feedback.

Given a piece of customer feedback, identify:
- sentiment: overall sentiment (positive, neutral, or negative)
- themes: 1-3 short topical phrases (e.g. "shipping", "service", "pricing")
- action_items: concrete improvements the company could make (0-3 items, can be empty)
- language: ISO 639-1 code of the feedback (e.g. "en", "es", "el")

Use the extract_insights tool to return your structured response.

Sentiment guidelines:

Classify according to what the feedback is PRIMARILY about. Identify the dominant intent first, then label.

- positive: primarily praise or satisfaction with what currently works. A small suggestion or minor caveat attached to clear praise stays positive ("Love the new dashboard, would be nice to also filter by date" → positive). A resolved past issue also classifies as positive — the resolution dominates.
- negative: primarily a complaint, blocker, or unresolved problem that prevents the user from getting value right now. When praise and an unresolved blocker appear together, the blocker dominates → negative.
- neutral: primarily a feature request, suggestion, or question — even when wrapped in enthusiastic or polite language ("would absolutely love a dark mode", "please add bulk export", "could you consider X"). Enthusiastic tone alone does NOT make a pure request positive: the user is asking for a change, not praising what exists.

Tie-breaker test: what is the user implicitly asking for?
- "Keep doing what you're doing" → positive.
- "Fix this thing" → negative.
- "Add this new thing" → neutral.

Theme guidelines:
- Use lowercase noun phrases.
- Return AT MOST 3 themes. Prefer 1-2 when the feedback has a single dominant topic; only use 3 when the feedback genuinely spans distinct concerns.
- Prefer concise canonical names: "shipping" over "shipping speed", "support" over "customer support team".
- Reuse the same canonical theme across synonyms. Pick the shortest common name and stick to it:
  - "quality", "product quality", "build quality" → "quality"
  - "support", "customer service", "service team", "support staff", "responsiveness" → "support"
  - "shipping", "shipping speed", "delivery time", "shipping delays" → "shipping"
  - "pricing", "pricing tiers", "plan pricing", "subscription pricing" → "pricing"
  Apply the same shortest-canonical-name principle to other synonym families you encounter.
- Keep each theme to 1-3 words at most.
- Ignore fictional, impossible, or exaggerated framings in the input (time travel, fantasy elements, multi-generational claims). Extract themes from the real underlying signal, not the literary device.

Action items:
- Imperative ("improve X", "fix Y") and specific.
- Must describe a change that is actionable in the present-day product. Do NOT parrot impossible or fictional framings from the input — e.g. "match historical standards from 1000 years ago" is not actionable; "improve product quality" is.
- Be grounded in what the feedback actually says — don't invent.
- Return an empty list when feedback is pure praise, pure observation, or has no specific change the company should make.
"""

VERSION = "extraction/v1.3"
