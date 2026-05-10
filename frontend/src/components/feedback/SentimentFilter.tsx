"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Sentiment } from "@/lib/api/types"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

export type SentimentFilterValue = Sentiment | "all"

interface SentimentFilterProps {
  value: SentimentFilterValue
  onChange: (value: SentimentFilterValue) => void
}

export function SentimentFilter({ value, onChange }: SentimentFilterProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">
        {feedbackCopy.filter.sentimentLabel}:
      </span>
      <Select
        value={value}
        onValueChange={(v) => onChange(v as SentimentFilterValue)}
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{feedbackCopy.filter.all}</SelectItem>
          <SelectItem value="positive">
            {feedbackCopy.filter.positive}
          </SelectItem>
          <SelectItem value="neutral">{feedbackCopy.filter.neutral}</SelectItem>
          <SelectItem value="negative">
            {feedbackCopy.filter.negative}
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
