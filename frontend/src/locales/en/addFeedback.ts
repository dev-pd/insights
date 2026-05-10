export const addFeedback = {
  page: {
    title: "Add Feedback",
    description:
      "Paste customer feedback to extract sentiment, themes, and action items.",
    bulkUploadNote:
      "Paste a single feedback item or multiple at once. CSV file upload is on the roadmap.",
  },
} as const

export type AddFeedback = typeof addFeedback
