"use client"

import { useSWRConfig } from "swr"

import { ProcessingPill } from "@/components/stats/ProcessingPill"
import { StatsDashboard } from "@/components/stats/StatsDashboard"
import { StressTestButton } from "@/components/stats/StressTestButton"
import { useDashboardStats } from "@/hooks/useDashboardStats"
import { useFeedbackStream } from "@/hooks/useFeedbackStream"
import { API_ROUTES } from "@/lib/api/routes"
import { stats as statsCopy } from "@/locales/en/stats"

export default function Home() {
  const { mutate } = useSWRConfig()

  // Stats fetch with idle-aware refresh interval. StatsDashboard subscribes
  // to the same key, so SWR dedupes — one HTTP poll per cycle serves both.
  const { data: stats } = useDashboardStats()

  const pendingCount = stats?.pending_count ?? 0

  // Conditional SSE: only subscribe while there's work in flight. When
  // pending=0 the SWR 5s poll handles dashboard freshness — no need to pin
  // a Redis pubsub slot just to receive heartbeats. When pending flips >0
  // (worker accepted a fresh batch via the stress-test button or /add),
  // the hook re-runs and opens the stream. Matches the architecture doc's
  // original "subscribe only when at least one row has status=processing"
  // intent.
  useFeedbackStream(
    {
      onStatsInvalidate: () => {
        mutate(API_ROUTES.stats)
      },
    },
    pendingCount > 0,
  )

  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">{statsCopy.kpis.sectionTitle}</h1>
        {/* Pill and button share the same slot: pill renders when items
            are processing, button when the pool is idle. Both components
            self-hide so the slot is always one element. */}
        {pendingCount > 0 ? (
          <ProcessingPill count={pendingCount} />
        ) : (
          <StressTestButton />
        )}
      </div>

      <StatsDashboard />
    </main>
  )
}
