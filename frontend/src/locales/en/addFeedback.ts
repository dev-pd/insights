export const addFeedback = {
  page: {
    title: "Add Feedback",
    description:
      "Paste customer feedback to extract sentiment, themes, and action items.",
    bulkUploadNote:
      "Paste a single feedback item or multiple at once. CSV file upload is on the roadmap.",
  },
  edgeCases: {
    title: "Edge cases tested",
    cases: [
      { label: "Absurd / impossible premise", text: "product worked 1000 yrs ago and now is bad" },
      { label: "Enthusiastic feature request", text: "would absolutely love a dark mode!" },
      { label: "Pure praise", text: "absolutely love this product, best purchase I've made all year!" },
      { label: "Resolved past-tense complaint", text: "had a billing issue last month, support fixed it within an hour" },
      { label: "Praise + unresolved blocker", text: "the UI is gorgeous but checkout is broken and I can't pay" },
      { label: "Polite suggestion", text: "Could you add a dark mode toggle? My eyes get tired using the bright interface at night." },
      { label: "Multi-issue complaint", text: "Shipping was slow, customer support did not reply for three days, and the product arrived damaged. I want a refund." },
      { label: "Non-English (Spanish)", text: "El producto es excelente pero el envío fue demasiado lento." },
      { label: "Vague / too short", text: "ok" },
      { label: "All-punctuation noise", text: "!@#$%^&*()_+" },
    ],
  },
} as const

export type AddFeedback = typeof addFeedback
