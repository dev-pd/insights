"use client"

import useSWR from "swr"

import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { HealthResponse } from "@/lib/api/types"
import { UI_TIMINGS } from "@/lib/constants"
import { common } from "@/locales/en/common"

export function HealthCheck() {
  const { data, error, isLoading } = useSWR<HealthResponse>(
    API_ROUTES.health,
    fetcher,
    { refreshInterval: UI_TIMINGS.healthCheckRefreshMs },
  )

  if (isLoading) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-gray-100 text-gray-600 text-sm">
        <span className="w-2 h-2 rounded-full bg-gray-400 animate-pulse" />
        {common.status.backendChecking}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-100 text-red-700 text-sm">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        {common.status.backendError}
      </div>
    )
  }

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-100 text-green-700 text-sm">
      <span className="w-2 h-2 rounded-full bg-green-500" />
      {common.status.backendOk}
    </div>
  )
}
