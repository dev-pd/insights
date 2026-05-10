export const feedback = {
  pasteForm: {
    title: "Paste customer feedback",
    placeholder:
      "Paste any customer feedback here. Reviews, support tickets, survey responses...",
    submitButton: "Extract insights",
    submittingButton: "Extracting...",
    helperText: "We'll extract sentiment, themes, and action items.",
  },
  list: {
    title: "Recent feedback",
    empty: "No feedback yet. Paste some above to get started.",
    loading: "Loading feedback...",
  },
  table: {
    columnTime: "Time",
    columnSentiment: "Sentiment",
    columnThemes: "Themes",
    columnPreview: "Preview",
    expandRow: "Expand row",
    collapseRow: "Collapse row",
    emptyMessage: "No feedback matches the current filter.",
    emptyAllMessage: "No feedback yet. Add some via the Add Feedback page.",
    showingCount: (start: number, end: number, total: number) =>
      `Showing ${start}-${end} of ${total}`,
    fullText: "Full text",
    createdAt: "Created",
    latency: "LLM latency",
    tokens: "Tokens",
    actionItemsLabel: "Action items",
    noActionItems: "No action items",
    skipReasonLabel: "Skip reason",
  },
  filter: {
    sentimentLabel: "Sentiment",
    all: "All sentiments",
    positive: "Positive",
    neutral: "Neutral",
    negative: "Negative",
  },
  pagination: {
    previous: "Previous",
    next: "Next",
    page: (current: number, total: number) => `Page ${current} of ${total}`,
    firstPage: "First",
    lastPage: "Last",
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
