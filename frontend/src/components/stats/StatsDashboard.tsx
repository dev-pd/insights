"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardStats } from "@/hooks/useDashboardStats"
import { common } from "@/locales/en/common"
import { stats as statsCopy } from "@/locales/en/stats"

import { KpiCard, type KpiTrend } from "./KpiCard"
import { SentimentTrendChart } from "./SentimentTrendChart"
import { SummaryWidget } from "./SummaryWidget"
import { ThemeFrequencyChart } from "./ThemeFrequencyChart"

const KPI_COUNT = 6

// Sub-5pp moves render as flat — small fluctuations look noisy on a small dataset.
const TREND_FLAT_THRESHOLD_PCT = 5

function trendDirection(deltaPct: number | null): KpiTrend | null {
  if (deltaPct === null) return null
  if (deltaPct > TREND_FLAT_THRESHOLD_PCT) return "up"
  if (deltaPct < -TREND_FLAT_THRESHOLD_PCT) return "down"
  return "flat"
}

function formatTokens(total: number): string {
  if (total < 1_000) return total.toString()
  if (total < 1_000_000) return `${(total / 1_000).toFixed(1)}k`
  return `${(total / 1_000_000).toFixed(1)}M`
}

export function StatsDashboard() {
  const { data, isLoading, error } = useDashboardStats()

  if (isLoading && !data) {
    return (
      <section className="flex flex-col gap-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {Array.from({ length: KPI_COUNT }).map((_, index) => (
            <Skeleton key={index} className="h-20 w-full" />
          ))}
        </div>
        <Skeleton className="h-32 w-full" />
        <div className="grid md:grid-cols-2 gap-4">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </section>
    )
  }

  if (error || !data) {
    return (
      <p className="text-sm text-destructive">
        {(error instanceof Error ? error.message : null) ??
          common.errors.generic}
      </p>
    )
  }

  const { sentiment_breakdown, today_delta, total_extracted } = data
  const sentimentShare = (count: number) =>
    statsCopy.kpis.sentimentShareHint(count, total_extracted)
  const totalTokens = data.total_input_tokens + data.total_output_tokens

  const kpis: Array<React.ComponentProps<typeof KpiCard>> = [
    {
      label: statsCopy.kpis.totalFeedback,
      value: data.total_feedback,
      hint: statsCopy.kpis.extractedHint(
        data.total_extracted,
        data.total_skipped,
        data.total_failed,
      ),
    },
    { label: statsCopy.kpis.positive, value: sentiment_breakdown.positive, hint: sentimentShare(sentiment_breakdown.positive) },
    { label: statsCopy.kpis.neutral, value: sentiment_breakdown.neutral, hint: sentimentShare(sentiment_breakdown.neutral) },
    { label: statsCopy.kpis.negative, value: sentiment_breakdown.negative, hint: sentimentShare(sentiment_breakdown.negative) },
    {
      label: statsCopy.kpis.today,
      value: today_delta.today_count,
      trend: trendDirection(today_delta.delta_pct),
      hint: statsCopy.kpis.dayOverDay(today_delta.delta_pct),
    },
    {
      label: statsCopy.kpis.totalTokens,
      value: formatTokens(totalTokens),
      hint: statsCopy.kpis.tokensHint(data.total_input_tokens, data.total_output_tokens),
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>

      <SummaryWidget />

      <div className="grid md:grid-cols-2 gap-4">
        <ThemeFrequencyChart themes={data.top_themes} />
        <SentimentTrendChart points={data.sentiment_trend} />
      </div>
    </section>
  )
}
