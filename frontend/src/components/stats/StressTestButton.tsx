"use client"

import { ZapIcon } from "lucide-react"
import { useState } from "react"
import { useSWRConfig } from "swr"

import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/useToast"
import { apiClient } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import type {
  StressTestRequest,
  StressTestResponse,
} from "@/lib/api/types"
import { stats as statsCopy } from "@/locales/en/stats"

const DEFAULT_STRESS_COUNT = 100

export function StressTestButton() {
  const [submitting, setSubmitting] = useState(false)
  const { showToast } = useToast()
  const { mutate } = useSWRConfig()

  const handleClick = async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      const result = await apiClient.post<StressTestResponse>(
        API_ROUTES.feedbackStressTest,
        { count: DEFAULT_STRESS_COUNT } satisfies StressTestRequest,
      )
      showToast(statsCopy.stressTest.successToast(result.dispatched), {
        variant: "success",
      })
      // Eagerly trigger a stats refetch so ProcessingPill takes over
      // immediately. Without this we'd wait ~1-2s for the first SSE
      // `stats_invalidate` to fire — during which the button briefly
      // flips back from "Adding..." to "Add 100 feedbacks" because
      // `pendingCount` is still 0 locally. Intentionally NOT resetting
      // `submitting` on success: the parent swaps in ProcessingPill the
      // moment pending_count > 0, unmounting this component.
      await mutate(API_ROUTES.stats)
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : statsCopy.stressTest.errorToast
      showToast(message, { variant: "error" })
      setSubmitting(false)
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleClick}
      disabled={submitting}
      title={statsCopy.stressTest.title}
      className="h-8 gap-1.5"
    >
      <ZapIcon className="size-3.5" aria-hidden="true" />
      {submitting
        ? statsCopy.stressTest.submitting
        : statsCopy.stressTest.buttonLabel(DEFAULT_STRESS_COUNT)}
    </Button>
  )
}
