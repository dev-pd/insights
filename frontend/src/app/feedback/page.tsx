"use client"

import { useState } from "react"
import useSWR, { useSWRConfig } from "swr"

import { FeedbackTable } from "@/components/feedback/FeedbackTable"
import { Pagination } from "@/components/feedback/Pagination"
import { SearchInput } from "@/components/feedback/SearchInput"
import {
  SentimentFilter,
  type SentimentFilterValue,
} from "@/components/feedback/SentimentFilter"
import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardStats } from "@/hooks/useDashboardStats"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import {
  useFeedbackStream,
  type FeedbackUpdateEvent,
} from "@/hooks/useFeedbackStream"
import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Feedback, FeedbackPaginatedResponse } from "@/lib/api/types"
import { UI_DIMENSIONS, UI_TIMINGS } from "@/lib/constants"
import { common } from "@/locales/en/common"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

const PAGE_SIZE = UI_DIMENSIONS.feedbackPageSize
const SKELETON_ROW_COUNT = 5

function buildPaginatedUrl(
  offset: number,
  sentiment: SentimentFilterValue,
  search: string,
) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(PAGE_SIZE),
  })
  if (sentiment !== "all") params.set("sentiment", sentiment)
  if (search) params.set("q", search)
  return `${API_ROUTES.feedbackPaginated}?${params.toString()}`
}

function applyFeedbackUpdate(
  current: FeedbackPaginatedResponse | undefined,
  event: FeedbackUpdateEvent,
): FeedbackPaginatedResponse | undefined {
  if (!current) return current
  const updatedItems = current.items.map((item: Feedback) => {
    if (item.id !== event.feedback_id) return item
    return {
      ...item,
      status: event.status as Feedback["status"],
      sentiment: (event.payload.sentiment as Feedback["sentiment"]) ?? item.sentiment,
      themes: event.payload.themes ?? item.themes,
      action_items: event.payload.action_items ?? item.action_items,
      language: event.payload.language ?? item.language,
    }
  })
  return { ...current, items: updatedItems }
}

export default function FeedbackPage() {
  const [page, setPage] = useState(1)
  const [sentimentFilter, setSentimentFilter] =
    useState<SentimentFilterValue>("all")
  const [searchInput, setSearchInput] = useState("")
  const debouncedSearch = useDebouncedValue(
    searchInput,
    UI_TIMINGS.feedbackSearchDebounceMs,
  )
  const trimmedSearch = debouncedSearch.trim()

  const { mutate } = useSWRConfig()

  const offset = (page - 1) * PAGE_SIZE
  const url = buildPaginatedUrl(offset, sentimentFilter, trimmedSearch)

  const { data, isLoading, error } = useSWR<FeedbackPaginatedResponse>(
    url,
    fetcher,
    {
      keepPreviousData: true,
    },
  )

  const { data: stats } = useDashboardStats()
  const sseEnabled = (stats?.pending_count ?? 0) > 0

  // Predicate-based mutate so one event patches every paginated key
  // currently cached (different offsets, filters, search strings).
  useFeedbackStream(
    {
      onFeedbackUpdate: (event) => {
        mutate<FeedbackPaginatedResponse>(
          (key) =>
            typeof key === "string" &&
            key.startsWith(API_ROUTES.feedbackPaginated),
          (current) => applyFeedbackUpdate(current, event),
          { revalidate: false },
        )
      },
      onStatsInvalidate: () => {
        mutate(API_ROUTES.stats)
      },
    },
    sseEnabled,
  )

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const hasActiveSearch = trimmedSearch.length > 0

  const handleFilterChange = (value: SentimentFilterValue) => {
    setSentimentFilter(value)
    setPage(1)
  }

  const handleSearchChange = (value: string) => {
    setSearchInput(value)
    setPage(1)
  }

  return (
    // Calc fills the viewport below the h-14 navbar. Header + pagination
    // sit outside the scroll region; only the table body scrolls.
    <main className="container mx-auto max-w-5xl px-4 py-6 flex flex-col gap-4 h-[calc(100vh-3.5rem)]">
      <header className="flex flex-col gap-3 flex-shrink-0">
        <h1 className="text-2xl font-bold">{feedbackCopy.list.title}</h1>

        <div className="flex items-center justify-between flex-wrap gap-3">
          <SearchInput value={searchInput} onChange={handleSearchChange} />
          <SentimentFilter
            value={sentimentFilter}
            onChange={handleFilterChange}
          />
        </div>

        {data && data.total > 0 && (
          <span className="text-sm text-muted-foreground tabular-nums">
            {hasActiveSearch
              ? feedbackCopy.search.resultCount(data.total, trimmedSearch)
              : feedbackCopy.table.showingCount(
                  offset + 1,
                  Math.min(offset + PAGE_SIZE, data.total),
                  data.total,
                )}
          </span>
        )}
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto -mx-4 px-4">
        {isLoading && !data ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: SKELETON_ROW_COUNT }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : common.errors.generic}
          </p>
        ) : !data || data.items.length === 0 ? (
          <div className="flex flex-col gap-2 py-8 text-center">
            {hasActiveSearch ? (
              <>
                <p className="text-base font-medium">
                  {feedbackCopy.search.noResultsTitle}
                </p>
                <p className="text-sm text-muted-foreground">
                  {feedbackCopy.search.noResultsHint(trimmedSearch)}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                {sentimentFilter === "all"
                  ? feedbackCopy.table.emptyAllMessage
                  : feedbackCopy.table.emptyMessage}
              </p>
            )}
          </div>
        ) : (
          <FeedbackTable items={data.items} />
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex-shrink-0 flex justify-center pt-2 border-t">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </div>
      )}
    </main>
  )
}
