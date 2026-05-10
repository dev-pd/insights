export const stats = {
  kpis: {
    sectionTitle: "Dashboard",
    totalFeedback: "Total feedback",
    positivePct: "Positive",
    negativePct: "Negative",
    today: "Today",
    avgLatency: "Avg latency",
    totalTokens: "Total tokens",
    dayOverDay: (delta: number | null) => {
      if (delta === null) return "vs yesterday: -"
      const sign = delta > 0 ? "+" : ""
      return `vs yesterday: ${sign}${delta.toFixed(1)}%`
    },
    // The hint now leads with `extracted` so users see the live-growing
    // count during a drain — that was previously implicit (total minus
    // skipped minus failed) and made the dashboard look stuck during a
    // stress test where total had already jumped at dispatch.
    extractedHint: (extracted: number, skipped: number, failed: number) =>
      `${extracted} extracted, ${skipped} skipped, ${failed} failed`,
    sentimentCountHint: (count: number) =>
      count === 1 ? "1 feedback item" : `${count} feedback items`,
    tokensHint: (input: number, output: number) =>
      `${input} in / ${output} out`,
    latencyHint: "LLM latency",
  },
  charts: {
    themeFrequency: {
      title: "Top themes",
      subtitle: "Last 7 days",
      emptyMessage: "No themes in the last 7 days yet.",
      countLabel: "Mentions",
    },
    sentimentTrend: {
      title: "Sentiment over time",
      subtitle: "Last 14 days",
      emptyMessage: "Not enough data for a trend yet.",
      legendPositive: "Positive",
      legendNeutral: "Neutral",
      legendNegative: "Negative",
    },
    sentimentBreakdown: {
      title: "Sentiment breakdown",
      positive: "Positive",
      neutral: "Neutral",
      negative: "Negative",
    },
  },
  processing: {
    pillLabel: (count: number) =>
      count === 1 ? "1 processing" : `${count} processing`,
  },
  stressTest: {
    buttonLabel: (count: number) => `Stress test (${count})`,
    submitting: "Dispatching...",
    successToast: (count: number) =>
      count === 1
        ? "Dispatched 1 synthetic feedback"
        : `Dispatched ${count} synthetic feedbacks`,
    errorToast: "Could not start stress test. Try again.",
    title: "Dispatch a batch of synthetic feedback to load-test the pipeline.",
  },
  summary: {
    title: "Today's summary",
    refreshButton: "Refresh",
    refreshing: "Refreshing...",
    refreshFailed: "Refresh failed. Try again.",
    updatedAgo: (minutes: number) => {
      if (minutes < 1) return "Updated just now"
      if (minutes < 60) return `Updated ${minutes}m ago`
      const hours = Math.floor(minutes / 60)
      return `Updated ${hours}h ago`
    },
    error: "Could not load summary. Try refreshing.",
    fromCache: "from cache",
  },
  units: {
    ms: "ms",
    tokens: "tokens",
    percent: "%",
  },
} as const

export type Stats = typeof stats
