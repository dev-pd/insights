export const stats = {
  kpis: {
    sectionTitle: "Dashboard",
    totalFeedback: "Total feedback",
    // Old 4-KPI keys are retained for one commit so the existing StatsDashboard
    // still type-checks; they're removed once the 6-KPI rewrite lands.
    extracted: "Extracted",
    skipped: "Skipped",
    failed: "Failed",
    // New 6-KPI keys
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
  units: {
    ms: "ms",
    tokens: "tokens",
    percent: "%",
  },
} as const

export type Stats = typeof stats
