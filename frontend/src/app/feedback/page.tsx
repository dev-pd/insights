"use client"

import { useState } from "react"
import useSWR from "swr"

import { FeedbackTable } from "@/components/feedback/FeedbackTable"
import { Pagination } from "@/components/feedback/Pagination"
import {
  SentimentFilter,
  type SentimentFilterValue,
} from "@/components/feedback/SentimentFilter"
import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { FeedbackPaginatedResponse } from "@/lib/api/types"
import { UI_DIMENSIONS } from "@/lib/constants"
import { common } from "@/locales/en/common"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

const PAGE_SIZE = UI_DIMENSIONS.feedbackPageSize
const SKELETON_ROW_COUNT = 5

function buildPaginatedUrl(offset: number, sentiment: SentimentFilterValue) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(PAGE_SIZE),
  })
  if (sentiment !== "all") params.set("sentiment", sentiment)
  return `${API_ROUTES.feedbackPaginated}?${params.toString()}`
}

export default function FeedbackPage() {
  const [page, setPage] = useState(1)
  const [sentimentFilter, setSentimentFilter] =
    useState<SentimentFilterValue>("all")

  const offset = (page - 1) * PAGE_SIZE
  const url = buildPaginatedUrl(offset, sentimentFilter)

  const { data, isLoading, error } = useSWR<FeedbackPaginatedResponse>(
    url,
    fetcher,
    {
      // Keep showing the previous page's rows during the brief refetch when
      // the user paginates or changes filters — no skeleton flash between pages.
      keepPreviousData: true,
    },
  )

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  const handleFilterChange = (value: SentimentFilterValue) => {
    setSentimentFilter(value)
    setPage(1)
  }

  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold">{feedbackCopy.list.title}</h1>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <SentimentFilter
            value={sentimentFilter}
            onChange={handleFilterChange}
          />
          {data && data.total > 0 && (
            <span className="text-sm text-muted-foreground tabular-nums">
              {feedbackCopy.table.showingCount(
                offset + 1,
                Math.min(offset + PAGE_SIZE, data.total),
                data.total,
              )}
            </span>
          )}
        </div>
      </header>

      {isLoading && !data ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: SKELETON_ROW_COUNT }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : common.errors.generic}
        </p>
      ) : !data || data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">
          {sentimentFilter === "all"
            ? feedbackCopy.table.emptyAllMessage
            : feedbackCopy.table.emptyMessage}
        </p>
      ) : (
        <>
          <FeedbackTable items={data.items} />

          {totalPages > 1 && (
            <div className="flex justify-center pt-4">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}
    </main>
  )
}
