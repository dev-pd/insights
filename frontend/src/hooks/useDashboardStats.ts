"use client"

import useSWR, { type SWRResponse } from "swr"

import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Stats } from "@/lib/api/types"
import { UI_TIMINGS } from "@/lib/constants"

// Adaptive poll: 5s when pending_count > 0, 30s when idle. Pairs with
// conditional-SSE in useFeedbackStream — active state pays for updates,
// idle minimizes traffic. SWR dedupes by cache key so multiple consumers
// share one HTTP poll.
export function useDashboardStats(): SWRResponse<Stats, Error> {
  return useSWR<Stats>(API_ROUTES.stats, fetcher, {
    refreshInterval: (latestData) =>
      (latestData?.pending_count ?? 0) > 0
        ? UI_TIMINGS.statsDashboardRefreshMs
        : UI_TIMINGS.statsDashboardIdleRefreshMs,
    revalidateOnFocus: true,
    keepPreviousData: true,
  })
}
