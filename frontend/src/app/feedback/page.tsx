"use client"

import { useState } from "react"
import useSWR from "swr"

import { FeedbackTable } from "@/components/feedback/FeedbackTable"
import { Pagination } from "@/components/feedback/Pagination"
import { SearchInput } from "@/components/feedback/SearchInput"
import {
  SentimentFilter,
  type SentimentFilterValue,
} from "@/components/feedback/SentimentFilter"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { fetcher } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { FeedbackPaginatedResponse } from "@/lib/api/types"
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

  const offset = (page - 1) * PAGE_SIZE
  const url = buildPaginatedUrl(offset, sentimentFilter, trimmedSearch)

  const { data, isLoading, error } = useSWR<FeedbackPaginatedResponse>(
    url,
    fetcher,
    {
      // Keep showing the previous results during the brief refetch when the
      // user paginates, changes filter, or types — no skeleton flash between
      // updates while the debounce/network round-trip resolves.
      keepPreviousData: true,
    },
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
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <header className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold">{feedbackCopy.list.title}</h1>

        <div className="flex flex-col gap-3">
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
        </div>
      </header>

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
