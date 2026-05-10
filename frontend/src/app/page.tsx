"use client"

import useSWR, { useSWRConfig } from "swr"

import { ProcessingPill } from "@/components/stats/ProcessingPill"
import { StatsDashboard } from "@/components/stats/StatsDashboard"
import { useFeedbackStream } from "@/hooks/useFeedbackStream"
import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Stats } from "@/lib/api/types"
import { UI_TIMINGS } from "@/lib/constants"
import { stats as statsCopy } from "@/locales/en/stats"

export default function Home() {
  const { mutate } = useSWRConfig()

  // Fetch stats just for the pending count — StatsDashboard runs its own
  // SWR fetch on the same key, so SWR deduplicates and serves both from a
  // single cache entry.
  const { data: stats } = useSWR<Stats>(API_ROUTES.stats, fetcher, {
    refreshInterval: UI_TIMINGS.statsDashboardRefreshMs,
    revalidateOnFocus: true,
  })

  // Listen for SSE stats_invalidate so the pill reflects worker completions
  // without waiting for the 5s SWR poll. /feedback page also listens, so a
  // user might end up with multiple SSE connections — that's fine, backend
  // serves each independently.
  useFeedbackStream({
    onStatsInvalidate: () => {
      mutate(API_ROUTES.stats)
    },
  })

  const pendingCount = stats?.pending_count ?? 0

  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">{statsCopy.kpis.sectionTitle}</h1>
        <ProcessingPill count={pendingCount} />
      </div>

      <StatsDashboard />
    </main>
  )
}
