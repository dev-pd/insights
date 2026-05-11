"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardStats } from "@/hooks/useDashboardStats"
import { common } from "@/locales/en/common"
import { stats as statsCopy } from "@/locales/en/stats"

import { KpiCard, type KpiTrend } from "./KpiCard"
import { SentimentTrendChart } from "./SentimentTrendChart"
import { SummaryWidget } from "./SummaryWidget"
import { ThemeFrequencyChart } from "./ThemeFrequencyChart"

const KPI_COUNT = 5

// Threshold for the "Today" trend arrow. Movement under this is rendered as
// flat — small fluctuations (1-2%) shouldn't trigger directional indicators
// because they look noisy on a small dataset.
const TREND_FLAT_THRESHOLD_PCT = 5

function trendDirection(deltaPct: number | null): KpiTrend | null {
  if (deltaPct === null) return null
  if (deltaPct > TREND_FLAT_THRESHOLD_PCT) return "up"
  if (deltaPct < -TREND_FLAT_THRESHOLD_PCT) return "down"
  return "flat"
}

export function StatsDashboard() {
  const { data, isLoading, error } = useDashboardStats()

  if (isLoading && !data) {
    return (
      <section className="flex flex-col gap-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
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

  const trend = trendDirection(data.today_delta.delta_pct)
  const extracted = data.total_extracted

  return (
    <section className="flex flex-col gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        <KpiCard
          label={statsCopy.kpis.totalFeedback}
          value={data.total_feedback}
          hint={statsCopy.kpis.extractedHint(
            data.total_extracted,
            data.total_skipped,
            data.total_failed,
          )}
        />
        <KpiCard
          label={statsCopy.kpis.positive}
          value={data.sentiment_breakdown.positive}
          hint={statsCopy.kpis.sentimentShareHint(
            data.sentiment_breakdown.positive,
            extracted,
          )}
        />
        <KpiCard
          label={statsCopy.kpis.neutral}
          value={data.sentiment_breakdown.neutral}
          hint={statsCopy.kpis.sentimentShareHint(
            data.sentiment_breakdown.neutral,
            extracted,
          )}
        />
        <KpiCard
          label={statsCopy.kpis.negative}
          value={data.sentiment_breakdown.negative}
          hint={statsCopy.kpis.sentimentShareHint(
            data.sentiment_breakdown.negative,
            extracted,
          )}
        />
        <KpiCard
          label={statsCopy.kpis.today}
          value={data.today_delta.today_count}
          trend={trend}
          hint={statsCopy.kpis.dayOverDay(data.today_delta.delta_pct)}
        />
      </div>

      <SummaryWidget />

      <div className="grid md:grid-cols-2 gap-4">
        <ThemeFrequencyChart themes={data.top_themes} />
        <SentimentTrendChart points={data.sentiment_trend} />
      </div>
    </section>
  )
}
