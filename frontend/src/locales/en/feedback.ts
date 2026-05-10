export const feedback = {
  pasteForm: {
    title: "Paste customer feedback",
    placeholder: "Paste any customer feedback here. Reviews, support tickets, survey responses...",
    submitButton: "Extract insights",
    submittingButton: "Extracting...",
    helperText: "We'll extract sentiment, themes, and action items.",
  },
  list: {
    title: "Recent feedback",
    empty: "No feedback yet. Paste some above to get started.",
    loading: "Loading feedback...",
  },
  card: {
    sentimentLabel: "Sentiment",
    themesLabel: "Themes",
    actionItemsLabel: "Action items",
    languageLabel: "Language",
    skippedLabel: "Skipped",
    skipReasonLabel: "Reason",
    processingLabel: "Processing...",
  },
  sentiment: {
    positive: "Positive",
    neutral: "Neutral",
    negative: "Negative",
  },
} as const

export type Feedback = typeof feedback
