"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { apiClient } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type { Feedback, FeedbackCreateRequest } from "@/lib/api/types"
import { UI_DIMENSIONS } from "@/lib/constants"
import { common } from "@/locales/en/common"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

interface PasteFormProps {
  onCreated: (feedback: Feedback) => void
}

export function PasteForm({ onCreated }: PasteFormProps) {
  const [text, setText] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    if (!text.trim() || submitting) return

    setSubmitting(true)
    setError(null)

    try {
      const result = await apiClient.post<Feedback>(API_ROUTES.feedback, {
        text: text.trim(),
      } satisfies FeedbackCreateRequest)

      onCreated(result)
      setText("")
    } catch (err) {
      setError(err instanceof Error ? err.message : common.errors.generic)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{feedbackCopy.pasteForm.title}</CardTitle>
        <CardDescription>{feedbackCopy.pasteForm.helperText}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={feedbackCopy.pasteForm.placeholder}
          rows={UI_DIMENSIONS.pasteFormRows}
          disabled={submitting}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button
          onClick={handleSubmit}
          disabled={!text.trim() || submitting}
          className="self-start"
        >
          {submitting
            ? feedbackCopy.pasteForm.submittingButton
            : feedbackCopy.pasteForm.submitButton}
        </Button>
      </CardContent>
    </Card>
  )
}
