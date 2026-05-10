export const stats = {
  kpis: {
    sectionTitle: "Dashboard",
    totalFeedback: "Total feedback",
    positivePct: "Positive",
    negativePct: "Negative",
    thisWeek: "This week",
    avgLatency: "Avg latency",
    totalTokens: "Total tokens",
    weekOverWeek: (delta: number | null) => {
      if (delta === null) return "vs last week: -"
      const sign = delta > 0 ? "+" : ""
      return `vs last week: ${sign}${delta.toFixed(1)}%`
    },
    extractedHint: (skipped: number, failed: number) =>
      `${skipped} skipped, ${failed} failed`,
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
