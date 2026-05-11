"""Extraction prompt v1.5 — three round-3 hardening fixes.

Round 3 red-team surfaced three failure modes in v1.4 (4/7 candidates passed,
overall 57.1%):

1. **Action-items suppressed by positive sentiment.** Praise + a specific ask
   was reading as "pure praise → empty action_items". Example:
   "Loving the app ❤️ Only wish: please add the ability to pin my top 3
   reports" → v1.4 returned 0 action items. The pin-reports request is a
   concrete, actionable change regardless of the surrounding praise. v1.4's
   action-item rule said "empty list when feedback is pure praise" without
   distinguishing pure praise from praise-plus-specific-ask. v1.5 makes
   action_items independent of sentiment: positive feedback can still
   produce action items when a concrete request appears.

2. **One-topic discipline didn't generalize to dev-API vocabulary.** The
   v1.4 synonym families enumerated support/shipping/pricing/quality but
   left technical domains uncovered. Example: "rate limit / 429s / quota /
   throttled" → v1.4 returned ['rate limiting', 'quota'] (2 themes for one
   API constraint). v1.5 adds an explicit rate-limit family and reinforces
   that one-topic discipline applies to technical synonyms too.

3. **Flat acknowledgment misclassified as positive.** "Works as expected.
   No issues so far." is the absence of problems, not praise. v1.4's
   tie-breaker only had branches for keep-doing / fix / add; nothing
   covered no-signal-either-way. v1.5 adds the explicit branch and
   clarifies that absence-of-problems is not positive evaluation.

All v1.4 guidance carries over verbatim. Only the three targeted additions.

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
- Ignore fictional, impossible, or exaggerated framings in the input (time travel, fantasy elements, multi-generational claims). Extract themes from the real underlying signal, not the literary device.

Action items:
- Imperative ("improve X", "fix Y") and specific.
- Must describe a change that is actionable in the present-day product. Do NOT parrot impossible or fictional framings from the input — e.g. "match historical standards from 1000 years ago" is not actionable; "improve product quality" is.
- Be grounded in what the feedback actually says — don't invent.
- **Action items are independent of sentiment.** Positive feedback can and should produce action items when the user names a specific actionable request, even casually ("only wish: add X", "would be cool if Y", "the one thing missing is Z"). Extract the request as an action item; the surrounding praise affects sentiment, not action-item presence.
- Return an empty list only when the feedback is pure praise with NO specific ask, pure observation, or has no specific change the company should make.
"""

VERSION = "extraction/v1.5"
