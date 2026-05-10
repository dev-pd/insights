export const feedback = {
  pasteForm: {
    title: "Paste customer feedback",
    placeholder:
      "Paste any customer feedback here. Reviews, support tickets, survey responses...",
    placeholderMultiple:
      "Paste multiple feedback items separated by blank lines.\n\nLike this.\n\nEach paragraph becomes a separate feedback item.",
    submitButton: "Extract insights",
    submittingButton: "Submitting...",
    helperText: "We'll extract sentiment, themes, and action items.",
    helperTextMultiple:
      "Separate items with a blank line. Or one per line if you prefer.",
    modeLabel: "Mode",
    modeSingle: "Single feedback",
    modeMultiple: "Multiple feedback items",
    detectedCount: (count: number) => {
      if (count === 0) return "No feedback detected"
      if (count === 1) return "1 feedback item detected"
      return `${count} feedback items detected`
    },
    maxBatchHint: (max: number) => `(max ${max} per batch)`,
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
  search: {
    placeholder: "Search feedback, themes, or actions...",
    ariaLabel: "Search feedback",
    clearButton: "Clear search",
    noResultsTitle: "No matches found",
    noResultsHint: (query: string) =>
      `No feedback matches "${query}". Try different terms or clear the search.`,
    resultCount: (count: number, query: string) =>
      count === 1
        ? `1 result for "${query}"`
        : `${count} results for "${query}"`,
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
  status: {
    processing: "Processing",
    failed: "Failed",
    skipped: "Skipped",
  },
  toast: {
    submitting: (count: number) =>
      count === 1 ? "Submitting feedback..." : `Submitting ${count} items...`,
    // Phase 4: extraction is async, so submission only confirms the row
    // was queued. The user sees the real result land on /feedback as the
    // worker completes (via SSE).
    successSingle: "Feedback queued for processing",
    successMultiple: (count: number) =>
      count === 1
        ? "1 item queued for processing"
        : `${count} items queued for processing`,
    error: "Could not submit feedback. Please try again.",
  },
} as const

export type Feedback = typeof feedback
