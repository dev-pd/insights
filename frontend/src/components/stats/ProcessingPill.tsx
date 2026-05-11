"use client"

import { Loader2Icon } from "lucide-react"

import { stats as statsCopy } from "@/locales/en/stats"

interface ProcessingPillProps {
  count: number
  total: number
}

export function ProcessingPill({ count, total }: ProcessingPillProps) {
  if (count <= 0) return null

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`${count} of ${total} feedback items processing`}
      className="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1.5 text-sm text-slate-700 dark:text-slate-200"
    >
      <span
        className="relative flex h-2 w-2 flex-shrink-0"
        aria-hidden="true"
      >
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-slate-400 dark:bg-slate-500 opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-slate-500 dark:bg-slate-400" />
      </span>
      <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
      <span className="tabular-nums">
        {statsCopy.processing.pillLabel(count, total)}
      </span>
    </div>
  )
}
