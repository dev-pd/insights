export const addFeedback = {
  page: {
    title: "Add Feedback",
    description:
      "Paste customer feedback to extract sentiment, themes, and action items.",
    bulkUploadNote:
      "Paste a single feedback item or multiple at once. CSV file upload is on the roadmap.",
  },
  edgeCases: {
    title: "Edge cases the extraction prompt is hardened against",
    intro:
      "Paste any of these above to see the extraction behave as described. Each one corresponds to a hand-curated case in the eval harness golden set.",
    cases: [
      {
        label: "Absurd / impossible premise",
        text: "product worked 1000 yrs ago and now is bad",
        expectation:
          "negative · themes stay grounded (e.g. 'quality') · action items don't echo the fictional framing",
      },
      {
        label: "Enthusiastic feature request",
        text: "would absolutely love a dark mode!",
        expectation:
          "neutral (it's a request, not praise — even though 'love' appears)",
      },
      {
        label: "Pure praise",
        text: "absolutely love this product, best purchase I've made all year!",
        expectation: "positive · no invented action items",
      },
      {
        label: "Resolved past-tense complaint",
        text: "had a billing issue last month, support fixed it within an hour",
        expectation:
          "positive (the resolution dominates) · no action items needed",
      },
      {
        label: "Praise + unresolved blocker",
        text: "the UI is gorgeous but checkout is broken and I can't pay",
        expectation:
          "negative · the blocker dominates · action item: fix checkout",
      },
      {
        label: "Polite suggestion",
        text: "Could you add a dark mode toggle? My eyes get tired using the bright interface at night.",
        expectation: "neutral · action items required (add dark mode)",
      },
      {
        label: "Multi-issue complaint",
        text: "Shipping was slow, customer support did not reply for three days, and the product arrived damaged. I want a refund.",
        expectation:
          "negative · multiple themes (shipping, support) · action items required",
      },
      {
        label: "Non-English (Spanish)",
        text: "El producto es excelente pero el envío fue demasiado lento.",
        expectation:
          "language detected (es) · negative sentiment · themes captured",
      },
      {
        label: "Vague / too short",
        text: "ok",
        expectation:
          "rejected at the validator — saved as 'skipped' with reason 'too_short', no LLM call",
      },
      {
        label: "All-punctuation noise",
        text: "!@#$%^&*()_+",
        expectation: "rejected as 'low_alpha_ratio' — no LLM call burned",
      },
    ],
  },
} as const

export type AddFeedback = typeof addFeedback
