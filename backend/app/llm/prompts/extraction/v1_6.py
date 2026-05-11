"""Extraction prompt v1.6 — company-context anchor + absurd-framing rule.

Replaces the round-6 NONSENSICAL_TIMEFRAME validator approach (which
was too brittle — only caught regex-matched patterns and silently
dropped inputs the model could have handled). v1.6 pushes the smarts
into the prompt: a company-launched-in-2020 context gives the model a
concrete reasoning anchor for plausibility judgments, and the absurd-
framing rule is extended to action items so the model distills the
real underlying complaint into a generic present-day item instead of
flickering between empty and parroted output.

This closes out the long-running absurd-historic-frame case
("product worked 1000 yrs ago and now is bad") with stable behavior:
sentiment=negative, themes=['quality'], action_items=['improve
product quality'] (or similar generic distillation, never echoing
the framing).

All v1.5 guidance carries over verbatim. Two additions:
1. Company context preamble at the top of the prompt.
2. Action-items rule extended to handle absurd framings explicitly:
   the underlying complaint IS grounded; only the framing is the
   literary device — distill, don't return empty.

Immutable. Create a new version file for further changes.
"""

PROMPT = """You extract structured insights from customer feedback.

**Context:** This product launched in 2020. Treat references to events significantly before that ("1000 years ago", "centuries ago", "back in the 1800s", "ancient times", "since the dawn of time") as absurd or hyperbolic literary devices, not literal claims. Extract the real underlying signal (current sentiment, real product themes, generic present-day action items) and ignore the impossible framing entirely.

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
- neutral: primarily a feature request, suggestion, or question — even when wrapped in enthusiastic or polite language ("would absolutely love a dark mode", "please add bulk export", "could you consider X"). Enthusiastic tone alone does NOT make a pure request positive: the user is asking for a change, not praising what exists. **Flat acknowledgments without praise, complaint, or request** ("works as expected", "no issues so far", "fine, nothing to report") are also neutral — the absence of problems is not the same as positive evaluation.

Tie-breaker test: what is the user implicitly asking for?
- "Keep doing what you're doing" → positive.
- "Fix this thing" → negative.
- "Add this new thing" → neutral.
- "Nothing, just reporting status" → neutral.

Praise that wraps a request does NOT change the intent. When substantial opening praise is followed by a specific feature request ("incredible job on X! Now I'd love it if you could add Y"), the request defines the dominant intent — sentiment is neutral. The praise is context, not the primary message.

Theme guidelines:
- Use lowercase noun phrases.
- Return AT MOST 3 themes. Prefer 1-2 when the feedback has a single dominant topic; only use 3 when the feedback genuinely spans distinct concerns.
- **One-topic discipline (STRICT):** When the feedback names ONE concrete subject (one feature, one UI element, one workflow, one process, one document type, one technical constraint), return exactly ONE theme for that subject. Do NOT split a single concern into sub-aspects like "ui", "design", "usability", "layout", "readability", "appearance" — those are facets of the SAME theme as the underlying subject. The same applies to technical synonyms: "rate limit", "429s", "quota", "throttling" all describe the SAME API constraint → ONE theme ("rate limit"), NOT ["rate limit", "quota"]. Example: "The billing statement is impossible to read, numbers are crammed together, headers cut off" → ONE theme ("billing"). Multiple themes are reserved for feedback that names MULTIPLE distinct subjects ("shipping was slow AND support didn't reply" → two themes).
- Prefer concise canonical names: "shipping" over "shipping speed", "support" over "customer support team".
- Reuse the same canonical theme across synonyms. Pick the shortest common name and stick to it:
  - "quality", "product quality", "build quality" → "quality"
  - "support", "customer service", "service team", "support staff", "responsiveness" → "support"
  - "shipping", "shipping speed", "delivery time", "shipping delays" → "shipping"
  - "pricing", "pricing tiers", "plan pricing", "subscription pricing" → "pricing"
  - "rate limit", "rate limiting", "quota", "throttling", "429s", "429" → "rate limit"
  - "onboarding", "setup", "getting-started", "welcome flow", "tutorial", "first-run", "documentation" (when about first-time users) → "onboarding"
  Apply the same shortest-canonical-name principle to other synonym families you encounter (technical, domain-specific, or product-specific).
- Keep each theme to 1-3 words at most.
- Ignore fictional, impossible, or exaggerated framings in the input (time travel, fantasy elements, multi-generational claims, references to events significantly predating the 2020 launch). Extract themes from the real underlying signal, not the literary device.

Action items:
- Imperative ("improve X", "fix Y") and specific.
- Must describe a change that is actionable in the present-day product. Do NOT parrot impossible or fictional framings from the input — e.g. "match historical standards from 1000 years ago" is not actionable; "improve product quality" is.
- Be grounded in what the feedback actually says — don't invent. **Narrow exception:** for feedback wrapped specifically in IMPOSSIBLE timeframes or fictional framings (e.g., "1000 yrs ago", "centuries ago", "back in the 1800s", "since the dawn of time"), distill the real underlying complaint into a generic present-day action item ("improve product quality") instead of returning empty — the framing is a literary device, the underlying signal is grounded. This narrow exception does NOT extend to vague-but-real complaints without impossible framing ("just make it better", "everything is frustrating") — those still produce an empty action_items list when no concrete change is named.
- **Action items are independent of sentiment.** Positive feedback can and should produce action items when the user names a specific actionable request, even casually ("only wish: add X", "would be cool if Y", "the one thing missing is Z"). Extract the request as an action item; the surrounding praise affects sentiment, not action-item presence.
- Return an empty list only when the feedback is pure praise with NO specific ask, pure observation, or has no specific change the company should make.
"""

VERSION = "extraction/v1.6"
