"use client"

import { RefreshCwIcon, SparklesIcon } from "lucide-react"
import { useState } from "react"
import useSWR from "swr"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/hooks/useToast"
import { apiClient, fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Summary } from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { common } from "@/locales/en/common"
import { stats as statsCopy } from "@/locales/en/stats"

const MS_PER_MINUTE = 60_000

function minutesSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / MS_PER_MINUTE)
}

interface WidgetHeaderProps {
  refreshing: boolean
  onRefresh?: () => void
}

function WidgetHeader({ refreshing, onRefresh }: WidgetHeaderProps) {
  return (
    <CardHeader
      className={cn(
        "flex flex-row items-center justify-between space-y-0",
        onRefresh && "pb-3",
      )}
    >
      <CardTitle className="text-base flex items-center gap-2">
        <SparklesIcon className="size-4 text-muted-foreground" />
        <span>{statsCopy.summary.title}</span>
      </CardTitle>
      {onRefresh && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={refreshing}
          className="h-8"
        >
          <RefreshCwIcon
            className={cn("size-3.5 mr-1.5", refreshing && "animate-spin")}
          />
          {refreshing
            ? statsCopy.summary.refreshing
            : statsCopy.summary.refreshButton}
        </Button>
      )}
    </CardHeader>
  )
}

export function SummaryWidget() {
  const [refreshing, setRefreshing] = useState(false)
  const { showToast } = useToast()

  const { data, isLoading, error, mutate } = useSWR<Summary>(
    API_ROUTES.summary,
    fetcher,
    {
      // Server owns freshness via Redis TTL — frontend doesn't poll.
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
    },
  )

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const fresh = await apiClient.post<Summary>(API_ROUTES.summaryRefresh, {})
      await mutate(fresh, { revalidate: false })
    } catch (refreshError) {
      const message =
        refreshError instanceof Error
          ? refreshError.message
          : statsCopy.summary.refreshFailed
      showToast(message, { variant: "error" })
    } finally {
      setRefreshing(false)
    }
  }

  if (isLoading && !data) {
    return (
      <Card>
        <WidgetHeader refreshing={false} />
        <CardContent className="flex flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card>
        <WidgetHeader refreshing={refreshing} onRefresh={handleRefresh} />
        <CardContent>
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : common.errors.generic}
          </p>
        </CardContent>
      </Card>
    )
  }

  const minutes = minutesSince(data.generated_at)
  const hasError = Boolean(data.error)

  return (
    <Card>
      <WidgetHeader refreshing={refreshing} onRefresh={handleRefresh} />
      <CardContent className="flex flex-col gap-3">
        <p
          className={cn(
            "text-sm min-h-[88px]",
            hasError
              ? "text-destructive"
              : "leading-relaxed text-foreground line-clamp-4",
          )}
        >
          {hasError ? statsCopy.summary.error : data.text}
        </p>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{statsCopy.summary.updatedAgo(minutes)}</span>
          {data.cached && (
            <>
              <span aria-hidden="true">·</span>
              <span>{statsCopy.summary.fromCache}</span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
