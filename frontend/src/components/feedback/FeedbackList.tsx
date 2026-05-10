"use client"

import useSWR from "swr"

import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Feedback } from "@/lib/api/types"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

import { FeedbackCard } from "./FeedbackCard"

export function FeedbackList() {
  const { data, isLoading, error } = useSWR<Feedback[]>(
    API_ROUTES.feedback,
    fetcher,
    {
      refreshInterval: 0,
      revalidateOnFocus: false,
    },
  )

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <p className="text-sm text-destructive">
        {error instanceof Error ? error.message : String(error)}
      </p>
    )
  }

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">{feedbackCopy.list.empty}</p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {data.map((item) => (
        <FeedbackCard key={item.id} feedback={item} />
      ))}
    </div>
  )
}
