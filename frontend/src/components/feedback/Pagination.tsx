"use client"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}

const MAX_VISIBLE_PAGES = 5

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: PaginationProps) {
  if (totalPages <= 1) return null

  // Build the visible page sequence: always show first + last, plus a window
  // around the current page. Insert "ellipsis" sentinels where the window
  // doesn't touch the endpoints. Threshold MAX_VISIBLE_PAGES + 2 covers the
  // case where we'd otherwise render 1 … 1 2 3 4 5 … 7 (the ellipses are
  // pointless when the window already touches both ends).
  const pages: (number | "ellipsis")[] = []

  if (totalPages <= MAX_VISIBLE_PAGES + 2) {
    for (let pageNumber = 1; pageNumber <= totalPages; pageNumber++) {
      pages.push(pageNumber)
    }
  } else {
    pages.push(1)
    const startVisible = Math.max(2, currentPage - 1)
    const endVisible = Math.min(totalPages - 1, currentPage + 1)
    if (startVisible > 2) pages.push("ellipsis")
    for (let pageNumber = startVisible; pageNumber <= endVisible; pageNumber++) {
      pages.push(pageNumber)
    }
    if (endVisible < totalPages - 1) pages.push("ellipsis")
    pages.push(totalPages)
  }

  return (
    <div className="flex items-center gap-1" role="navigation" aria-label="Pagination">
      <Button
        variant="outline"
        size="sm"
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        {feedbackCopy.pagination.previous}
      </Button>

      {pages.map((page, index) => {
        if (page === "ellipsis") {
          return (
            <span
              key={`ellipsis-${index}`}
              className="px-2 text-muted-foreground"
              aria-hidden="true"
            >
              ...
            </span>
          )
        }
        const isCurrent = page === currentPage
        return (
          <Button
            key={page}
            variant={isCurrent ? "default" : "outline"}
            size="sm"
            aria-current={isCurrent ? "page" : undefined}
            onClick={() => onPageChange(page)}
            className={cn("min-w-[2rem]", isCurrent && "pointer-events-none")}
          >
            {page}
          </Button>
        )
      })}

      <Button
        variant="outline"
        size="sm"
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        {feedbackCopy.pagination.next}
      </Button>
    </div>
  )
}
