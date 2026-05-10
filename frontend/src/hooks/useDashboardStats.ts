"use client"

import useSWR, { type SWRResponse } from "swr"

import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Stats } from "@/lib/api/types"
import { UI_TIMINGS } from "@/lib/constants"

/**
 * SWR-cached `/v1/stats` fetch with a refresh interval that adapts to
 * `pending_count`:
 *
 *   - `pending_count > 0` (active drain): fast poll (5s)
 *   - `pending_count = 0` (idle):         slow poll (30s)
 *
 * Matches the conditional-SSE pattern from useFeedbackStream — active
 * state pays for snappy updates, idle state minimizes background work.
 * Without this, an idle dashboard burns ~14 requests/minute on /stats
 * + /health polls for no observable benefit (data isn't changing).
 *
 * Use this everywhere /v1/stats is needed (home page, feedback page,
 * StatsDashboard). SWR dedupes by cache key (`API_ROUTES.stats`), so
 * multiple consumers in the same tab share one HTTP poll. Centralizing
 * the config here keeps the active/idle interval semantics consistent
 * across call sites.
 */
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
