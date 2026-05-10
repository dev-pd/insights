"use client"

import useSWR from "swr"

import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Stats } from "@/lib/api/types"
import { UI_FORMATTING, UI_TIMINGS } from "@/lib/constants"
import { common } from "@/locales/en/common"
import { stats as statsCopy } from "@/locales/en/stats"

import { KpiCard } from "./KpiCard"
import { SentimentTrendChart } from "./SentimentTrendChart"
import { ThemeFrequencyChart } from "./ThemeFrequencyChart"

function formatTokens(total: number): string {
  const threshold = UI_FORMATTING.tokensKThreshold
  if (total < threshold) return total.toString()
  return `${(total / threshold).toFixed(1)}k`
}

function formatLatency(value: number | null): string {
  if (value === null) return "-"
  return Math.round(value).toString()
}

export function StatsDashboard() {
  const { data, isLoading, error } = useSWR<Stats>(API_ROUTES.stats, fetcher, {
    refreshInterval: UI_TIMINGS.statsDashboardRefreshMs,
    revalidateOnFocus: true,
    keepPreviousData: true,
  })

  if (isLoading && !data) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">{statsCopy.kpis.sectionTitle}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </section>
    )
  }

  if (error || !data) {
    return (
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">{statsCopy.kpis.sectionTitle}</h2>
        <p className="text-sm text-destructive">
          {(error instanceof Error ? error.message : null) ?? common.errors.generic}
        </p>
      </section>
    )
  }

  const totalTokens = data.total_input_tokens + data.total_output_tokens

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{statsCopy.kpis.sectionTitle}</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label={statsCopy.kpis.totalFeedback}
          value={data.total_feedback}
        />
        <KpiCard
          label={statsCopy.kpis.extracted}
          value={data.total_extracted}
          hint={`${data.total_skipped} skipped, ${data.total_failed} failed`}
        />
        <KpiCard
          label={statsCopy.kpis.avgLatency}
          value={formatLatency(data.avg_latency_ms)}
          unit={statsCopy.units.ms}
        />
        <KpiCard
          label={statsCopy.kpis.totalTokens}
          value={formatTokens(totalTokens)}
          hint={`${data.total_input_tokens} in / ${data.total_output_tokens} out`}
        />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <ThemeFrequencyChart themes={data.top_themes} />
        <SentimentTrendChart points={data.sentiment_trend} />
      </div>
    </section>
  )
}
