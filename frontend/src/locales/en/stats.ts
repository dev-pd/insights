export const stats = {
  kpis: {
    totalFeedback: "Total feedback",
    avgSentiment: "Average sentiment",
    topTheme: "Top theme",
    processingRate: "Processing rate",
  },
  charts: {
    themeFrequency: {
      title: "Theme frequency",
      emptyMessage: "No themes yet.",
    },
    sentimentTrend: {
      title: "Sentiment over time",
      emptyMessage: "Not enough data for a trend.",
    },
  },
} as const

export type Stats = typeof stats
