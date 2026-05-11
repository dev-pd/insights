"use client"

import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/hooks/useToast"
import { apiClient } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type {
  Feedback,
  FeedbackBatchRequest,
  FeedbackBatchResponse,
  FeedbackCreateRequest,
} from "@/lib/api/types"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

type Mode = "single" | "multiple"

const MAX_BATCH_SIZE = 50
const ROWS_SINGLE = 8
const ROWS_MULTIPLE = 12
const SUBMITTING_TOAST_DURATION_MS = 2500

const MODE_OPTIONS: ReadonlyArray<{ value: Mode; label: string }> = [
  { value: "single", label: feedbackCopy.pasteForm.modeSingle },
  { value: "multiple", label: feedbackCopy.pasteForm.modeMultiple },
]

function splitFeedbackTexts(text: string): string[] {
  // Blank-line split first (paragraphs / Slack copy), then single-newline
  // (spreadsheet columns), then treat as one feedback.
  const paragraphs = text
    .split(/\n\s*\n+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
  if (paragraphs.length > 1) return paragraphs

  const lines = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (lines.length > 1) return lines

  const trimmed = text.trim()
  return trimmed ? [trimmed] : []
}

interface PasteFormProps {
  onCreated: (feedback: Feedback) => void
}

export function PasteForm({ onCreated }: PasteFormProps) {
  const [text, setText] = useState("")
  // Default "multiple": single-mode silently lumped multi-paragraph pastes
  // into one row (real bug seen: two distinct comments → one feedback).
  // The splitter handles single-item input fine via /v1/feedback/batch.
  const [mode, setMode] = useState<Mode>("multiple")
  const [submitting, setSubmitting] = useState(false)
  const { showToast } = useToast()

  const detectedCount = useMemo(() => {
    if (mode === "single") return text.trim() ? 1 : 0
    return splitFeedbackTexts(text).length
  }, [text, mode])

  const exceedsBatchLimit = detectedCount > MAX_BATCH_SIZE
  const canSubmit =
    !submitting &&
    text.trim().length > 0 &&
    detectedCount > 0 &&
    !exceedsBatchLimit

  const handleSubmit = async () => {
    if (!canSubmit) return
    setSubmitting(true)

    try {
      if (mode === "single") {
        const result = await apiClient.post<Feedback>(API_ROUTES.feedback, {
          text: text.trim(),
        } satisfies FeedbackCreateRequest)
        onCreated(result)
        setText("")
        showToast(feedbackCopy.toast.successSingle, { variant: "success" })
      } else {
        const texts = splitFeedbackTexts(text)
        showToast(feedbackCopy.toast.submitting(texts.length), {
          variant: "info",
          durationMs: SUBMITTING_TOAST_DURATION_MS,
        })
        const result = await apiClient.post<FeedbackBatchResponse>(
          API_ROUTES.feedbackBatch,
          { texts } satisfies FeedbackBatchRequest,
        )
        for (const item of result.items) {
          onCreated(item)
        }
        setText("")
        showToast(feedbackCopy.toast.successMultiple(result.total), {
          variant: "success",
        })
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : feedbackCopy.toast.error
      showToast(message, { variant: "error" })
    } finally {
      setSubmitting(false)
    }
  }

  const placeholder =
    mode === "single"
      ? feedbackCopy.pasteForm.placeholder
      : feedbackCopy.pasteForm.placeholderMultiple

  const helperText =
    mode === "single"
      ? feedbackCopy.pasteForm.helperText
      : feedbackCopy.pasteForm.helperTextMultiple

  return (
    <Card>
      <CardHeader>
        <CardTitle>{feedbackCopy.pasteForm.title}</CardTitle>
        <CardDescription>{helperText}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {/* Native radio over a custom toggle — the styling burden isn't
            worth what we already get from the platform's a11y/keyboard. */}
        <fieldset className="flex items-center gap-4 flex-wrap">
          <Label className="text-sm font-medium">
            {feedbackCopy.pasteForm.modeLabel}:
          </Label>
          <div className="flex items-center gap-4">
            {MODE_OPTIONS.map(({ value, label }) => (
              <label
                key={value}
                className="flex items-center gap-1.5 cursor-pointer"
              >
                <input
                  type="radio"
                  name="paste-mode"
                  value={value}
                  checked={mode === value}
                  onChange={() => setMode(value)}
                  disabled={submitting}
                  className="h-4 w-4"
                />
                <span className="text-sm">{label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <Textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={placeholder}
          rows={mode === "multiple" ? ROWS_MULTIPLE : ROWS_SINGLE}
          disabled={submitting}
          className="resize-y font-mono text-sm"
        />

        {mode === "multiple" && text.trim().length > 0 && (
          <div className="flex items-center justify-between text-sm gap-2">
            <span
              className={
                exceedsBatchLimit
                  ? "text-destructive font-medium"
                  : "text-muted-foreground"
              }
            >
              {feedbackCopy.pasteForm.detectedCount(detectedCount)}
              {exceedsBatchLimit &&
                ` ${feedbackCopy.pasteForm.maxBatchHint(MAX_BATCH_SIZE)}`}
            </span>
          </div>
        )}

        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="self-start min-w-32"
        >
          {submitting
            ? feedbackCopy.pasteForm.submittingButton
            : feedbackCopy.pasteForm.submitButton}
        </Button>
      </CardContent>
    </Card>
  )
}
