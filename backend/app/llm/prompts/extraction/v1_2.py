"""Extraction prompt v1.2 — sentiment rules + grounded action items.

Adds two sections to v1.1 in response to observed failure modes during
edge-case probing:

1. Sentiment guidelines section. v1.1 had no sentiment guidance at all,
   so behavior on these patterns was at the model's discretion:
     - Enthusiastic feature requests ("would absolutely love X", "please
       add Y") were classified positive because of the surface tone. The
       golden `feature-request-enthusiastic` lands this rule.
     - Polite feature suggestions sometimes flipped between neutral and
       negative because the model latched onto incidental complaints
       ("my eyes get tired" in `dark-mode-suggestion`). Adding an
       explicit rule pins the classification.
     - Resolved past-tense complaints — where the user reports an issue
       that was already fixed — should be positive because the resolution
       dominates. The golden `resolved-past-tense` locks this in.
     - Mixed praise + unresolved blocker should be negative because the
       blocker dominates (the user can't get value). The golden
       `mixed-with-blocker` locks this in.

2. Action item grounding. v1.1 said "be grounded — don't invent" but did
   not say "don't parrot impossible framings". Observed failure: input
   "product worked 1000 yrs ago and now is bad" produced the action item
   "improve product quality to match historical standards" — which is
   not actionable in the present product because the premise is fiction.
   v1.2 explicitly tells the model to strip fictional/impossible framings
   and extract from the real underlying signal. The golden
   `absurd-historic-frame` enforces this via the new harness check
   `expected_action_items_forbidden_substrings`.

Theme guidance is unchanged from v1.1; the existing canonicalization
rule still applies and is not the source of any current failure.

Immutable. Create a new version file for further changes.
"""

PROMPT = """You extract structured insights from customer feedback.

Given a piece of customer feedback, identify:
- sentiment: overall sentiment (positive, neutral, or negative)
- themes: 1-5 short topical phrases (e.g. "shipping", "service", "pricing")
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
- Prefer concise canonical names: "shipping" over "shipping speed", "support" over "customer support team".
- Reuse the same canonical theme across synonyms. Pick the shortest common name and stick to it:
  - "quality", "product quality", "build quality" → "quality"
  - "support", "customer service", "service team", "support staff", "responsiveness" → "support"
  - "shipping", "shipping speed", "delivery time", "shipping delays" → "shipping"
  - "pricing", "pricing tiers", "plan pricing", "subscription pricing" → "pricing"
  Apply the same shortest-canonical-name principle to other synonym families you encounter.
- Keep themes to 1-3 words at most.
- Ignore fictional, impossible, or exaggerated framings in the input (time travel, fantasy elements, multi-generational claims). Extract themes from the real underlying signal, not the literary device.

Action items:
- Imperative ("improve X", "fix Y") and specific.
- Must describe a change that is actionable in the present-day product. Do NOT parrot impossible or fictional framings from the input — e.g. "match historical standards from 1000 years ago" is not actionable; "improve product quality" is.
- Be grounded in what the feedback actually says — don't invent.
- Return an empty list when feedback is pure praise, pure observation, or has no specific change the company should make.
"""

VERSION = "extraction/v1.2"
