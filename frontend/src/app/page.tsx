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
  const { data: stats } = useDashboardStats()
  const pendingCount = stats?.pending_count ?? 0

  // SSE only while pending > 0 — idle dashboards rely on the SWR poll
  // and don't pin a Redis pubsub slot.
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
