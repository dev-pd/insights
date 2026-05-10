"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardStats } from "@/hooks/useDashboardStats"
import { UI_FORMATTING } from "@/lib/constants"
import { common } from "@/locales/en/common"
import { stats as statsCopy } from "@/locales/en/stats"

import { KpiCard, type KpiTrend } from "./KpiCard"
import { SentimentTrendChart } from "./SentimentTrendChart"
import { SummaryWidget } from "./SummaryWidget"
import { ThemeFrequencyChart } from "./ThemeFrequencyChart"

const KPI_COUNT = 6

// Threshold for "this week" trend arrow. Movement under this is rendered as
// flat — small fluctuations (1-2%) shouldn't trigger directional indicators
// because they look noisy on a small dataset.
const TREND_FLAT_THRESHOLD_PCT = 5

const TOKENS_M_THRESHOLD = 1_000_000

function formatTokens(total: number): string {
  const kThreshold = UI_FORMATTING.tokensKThreshold
  if (total < kThreshold) return total.toString()
  if (total < TOKENS_M_THRESHOLD) return `${(total / kThreshold).toFixed(1)}k`
  return `${(total / TOKENS_M_THRESHOLD).toFixed(1)}M`
}

function formatLatency(value: number | null): string {
  if (value === null) return "-"
  return Math.round(value).toString()
}

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

  const totalTokens = data.total_input_tokens + data.total_output_tokens
  const trend = trendDirection(data.today_delta.delta_pct)

  return (
    <section className="flex flex-col gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
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
          label={statsCopy.kpis.positivePct}
          value={data.positive_pct.toFixed(0)}
          unit={statsCopy.units.percent}
          hint={statsCopy.kpis.sentimentCountHint(
            data.sentiment_breakdown.positive,
          )}
        />
        <KpiCard
          label={statsCopy.kpis.negativePct}
          value={data.negative_pct.toFixed(0)}
          unit={statsCopy.units.percent}
          hint={statsCopy.kpis.sentimentCountHint(
            data.sentiment_breakdown.negative,
          )}
        />
        <KpiCard
          label={statsCopy.kpis.today}
          value={data.today_delta.today_count}
          trend={trend}
          hint={statsCopy.kpis.dayOverDay(data.today_delta.delta_pct)}
        />
        <KpiCard
          label={statsCopy.kpis.avgLatency}
          value={formatLatency(data.avg_latency_ms)}
          unit={statsCopy.units.ms}
          hint={statsCopy.kpis.latencyHint}
        />
        <KpiCard
          label={statsCopy.kpis.totalTokens}
          value={formatTokens(totalTokens)}
          hint={statsCopy.kpis.tokensHint(
            data.total_input_tokens,
            data.total_output_tokens,
          )}
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
