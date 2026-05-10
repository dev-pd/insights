export const addFeedback = {
  page: {
    title: "Add Feedback",
    description:
      "Paste customer feedback to extract sentiment, themes, and action items.",
    bulkUploadNote:
      "Bulk upload is coming soon. For now, paste feedback one at a time.",
  },
} as const

export type AddFeedback = typeof addFeedback
