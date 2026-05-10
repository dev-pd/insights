export const stats = {
  kpis: {
    sectionTitle: "Dashboard",
    totalFeedback: "Total feedback",
    extracted: "Extracted",
    skipped: "Skipped",
    failed: "Failed",
    avgLatency: "Avg LLM latency",
    totalTokens: "Total tokens",
  },
  charts: {
    themeFrequency: {
      title: "Top themes",
      subtitle: "Most common themes across all feedback",
      emptyMessage: "No themes yet. Add feedback to see themes appear.",
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
  },
} as const

export type Stats = typeof stats
