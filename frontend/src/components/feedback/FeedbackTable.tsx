"use client"

import { formatDistanceToNowStrict } from "date-fns"
import {
  ChevronDownIcon,
  ChevronRightIcon,
  Loader2Icon,
} from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { Feedback, Sentiment } from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

const PREVIEW_MAX_CHARS = 80
const RELATIVE_TIME_MAX_DAYS = 7
const THEMES_PREVIEW_MAX = 3

const sentimentBadgeVariant: Record<
  Sentiment,
  "default" | "secondary" | "destructive"
> = {
  positive: "default",
  neutral: "secondary",
  negative: "destructive",
}

const sentimentLabel: Record<Sentiment, string> = {
  positive: feedbackCopy.sentiment.positive,
  neutral: feedbackCopy.sentiment.neutral,
  negative: feedbackCopy.sentiment.negative,
}

const TH_BASE_CLASS =
  "sticky top-0 z-10 bg-muted text-left font-medium text-muted-foreground px-3 py-2 border-b"

const COLUMNS: ReadonlyArray<{ label?: string; widthClass?: string; hideOnMobile?: boolean }> = [
  { label: feedbackCopy.table.columnTime, widthClass: "w-32" },
  { label: feedbackCopy.table.columnSentiment, widthClass: "w-32" },
  { label: feedbackCopy.table.columnThemes, widthClass: "w-64", hideOnMobile: true },
  { label: feedbackCopy.table.columnPreview },
  { widthClass: "w-12" },
]

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text
  return `${text.slice(0, maxChars).trim()}...`
}

function formatRelativeTime(iso: string): string {
  const date = new Date(iso)
  const ageDays = (Date.now() - date.getTime()) / (1000 * 60 * 60 * 24)
  if (ageDays >= RELATIVE_TIME_MAX_DAYS) return date.toLocaleDateString()
  return `${formatDistanceToNowStrict(date)} ago`
}

interface FeedbackTableProps {
  items: Feedback[]
}

export function FeedbackTable({ items }: FeedbackTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  if (items.length === 0) return null

  return (
    <div className="rounded-md border">
      <table className="w-full text-sm border-separate border-spacing-0 table-fixed">
        <thead className="bg-muted">
          <tr>
            {COLUMNS.map((col, index) => (
              <th
                key={index}
                aria-hidden={col.label ? undefined : "true"}
                className={cn(
                  TH_BASE_CLASS,
                  col.widthClass,
                  col.hideOnMobile && "hidden md:table-cell",
                )}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <FeedbackRow
              key={item.id}
              item={item}
              isExpanded={expandedIds.has(item.id)}
              onToggle={() => toggleExpand(item.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface FeedbackRowProps {
  item: Feedback
  isExpanded: boolean
  onToggle: () => void
}

function FeedbackRow({ item, isExpanded, onToggle }: FeedbackRowProps) {
  return (
    <>
      <tr
        className={cn(
          "border-b last:border-0 cursor-pointer hover:bg-muted/30 transition-colors",
          isExpanded && "bg-muted/30",
        )}
        onClick={onToggle}
      >
        <td className="px-3 py-2 text-muted-foreground tabular-nums whitespace-nowrap">
          {formatRelativeTime(item.created_at)}
        </td>
        <td className="px-3 py-2">
          <StatusBadge item={item} />
        </td>
        <td className="px-3 py-2 hidden md:table-cell">
          {item.themes.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {item.themes.slice(0, THEMES_PREVIEW_MAX).map((theme) => (
                <span
                  key={theme}
                  className="text-xs px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground"
                >
                  {theme}
                </span>
              ))}
              {item.themes.length > THEMES_PREVIEW_MAX && (
                <span className="text-xs text-muted-foreground self-center">
                  +{item.themes.length - THEMES_PREVIEW_MAX}
                </span>
              )}
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">-</span>
          )}
        </td>
        <td className="px-3 py-2 text-foreground truncate max-w-0">
          {truncate(item.text, PREVIEW_MAX_CHARS)}
        </td>
        <td className="px-3 py-2">
          <Button
            variant="ghost"
            size="sm"
            aria-label={
              isExpanded
                ? feedbackCopy.table.collapseRow
                : feedbackCopy.table.expandRow
            }
            aria-expanded={isExpanded}
            onClick={(event) => {
              event.stopPropagation()
              onToggle()
            }}
            className="h-7 w-7 p-0"
          >
            {isExpanded ? (
              <ChevronDownIcon className="size-4" />
            ) : (
              <ChevronRightIcon className="size-4" />
            )}
          </Button>
        </td>
      </tr>
      {isExpanded && (
        <tr className="border-b last:border-0 bg-muted/20">
          <td colSpan={5} className="px-3 py-4">
            <FeedbackRowDetail item={item} />
          </td>
        </tr>
      )}
    </>
  )
}

function StatusBadge({ item }: { item: Feedback }) {
  if (item.status === "extracted" && item.sentiment) {
    return (
      <Badge variant={sentimentBadgeVariant[item.sentiment]}>
        {sentimentLabel[item.sentiment]}
      </Badge>
    )
  }
  if (item.status === "processing") {
    return (
      <Badge variant="outline" className="gap-1.5">
        <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
        {feedbackCopy.status.processing}
      </Badge>
    )
  }
  if (item.status === "failed") {
    return <Badge variant="destructive">{feedbackCopy.status.failed}</Badge>
  }
  if (item.status === "skipped") {
    return <Badge variant="secondary">{feedbackCopy.status.skipped}</Badge>
  }
  return <span className="text-xs text-muted-foreground">{item.status}</span>
}

function FeedbackRowDetail({ item }: { item: Feedback }) {
  const meta = item.llm_metadata
  const latencyMs = meta?.latency_ms
  const inputTokens = meta?.input_tokens
  const outputTokens = meta?.output_tokens

  return (
    <div className="flex flex-col gap-3 max-w-3xl">
      <div>
        <div className="text-xs text-muted-foreground mb-1">
          {feedbackCopy.table.fullText}
        </div>
        <p className="text-sm whitespace-pre-wrap">{item.text}</p>
      </div>

      {item.themes.length > 0 && (
        <div className="flex items-start gap-2">
          <span className="text-xs text-muted-foreground mt-0.5">
            {feedbackCopy.card.themesLabel}:
          </span>
          <div className="flex flex-wrap gap-1">
            {item.themes.map((theme) => (
              <Badge key={theme} variant="outline" className="text-xs">
                {theme}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {item.action_items.length > 0 ? (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">
            {feedbackCopy.table.actionItemsLabel}:
          </span>
          <ul className="list-disc list-inside text-sm">
            {item.action_items.map((action, index) => (
              <li key={index}>{action}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">
          {feedbackCopy.table.noActionItems}
        </div>
      )}

      {item.skip_reason && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {feedbackCopy.table.skipReasonLabel}:
          </span>
          <Badge variant="secondary" className="text-xs">
            {item.skip_reason}
          </Badge>
        </div>
      )}

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground pt-2 border-t">
        <span>
          {feedbackCopy.table.createdAt}:{" "}
          {new Date(item.created_at).toLocaleString()}
        </span>
        {latencyMs !== undefined && (
          <span>
            {feedbackCopy.table.latency}: {latencyMs}ms
          </span>
        )}
        {inputTokens !== undefined && outputTokens !== undefined && (
          <span>
            {feedbackCopy.table.tokens}: {inputTokens} in / {outputTokens} out
          </span>
        )}
        {item.language && (
          <span>
            {feedbackCopy.card.languageLabel}: {item.language}
          </span>
        )}
      </div>
    </div>
  )
}
