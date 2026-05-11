"""Extraction prompt v1.4 — single-topic discipline.

The 40-case red-team round surfaced a real over-extraction tendency:
"The billing statement is impossible to read. The numbers are crammed
together with no spacing and the column headers are cut off." → v1.3
returned ['billing', 'ui design'] (or 'billing', 'readability', etc.)
when there's clearly ONE concern — the billing statement's readability.

v1.3 said "Prefer 1-2 when the feedback has a single dominant topic"
but the soft "prefer" wording didn't enforce it. The model treated UI /
design / usability as separate themes from the underlying subject
('billing') even when they describe the SAME issue.

v1.4 hardens the rule: when the feedback names ONE concrete subject,
return exactly ONE theme for it. Sub-aspects of a single concern
(ui / design / layout / usability) collapse into the parent theme,
not separate themes. Multiple themes are reserved for genuinely
distinct subjects (shipping AND support, or billing AND login).

This rule also tightens cases like sentiment-formal-complaint where
v1.3 returned 'subscription renewal' + 'support' for a complaint that's
really about renewal-billing — those are two facets of the same
process, not two distinct concerns.

All v1.3 guidance carries over verbatim except the single new
'One-topic discipline' bullet.

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
- **One-topic discipline (STRICT):** When the feedback names ONE concrete subject (one feature, one UI element, one workflow, one process, one document type), return exactly ONE theme for that subject. Do NOT split a single concern into sub-aspects like "ui", "design", "usability", "layout", "readability", "appearance" — those are facets of the SAME theme as the underlying subject. Example: "The billing statement is impossible to read, numbers are crammed together, headers cut off" → ONE theme ("billing"), NOT ["billing", "ui"] or ["billing", "design"]. Multiple themes are reserved for feedback that names MULTIPLE distinct subjects ("shipping was slow AND support didn't reply" → two themes).
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

VERSION = "extraction/v1.4"
