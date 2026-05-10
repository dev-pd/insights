"use client"

import { mutate } from "swr"

import { FeedbackList } from "@/components/feedback/FeedbackList"
import { PasteForm } from "@/components/feedback/PasteForm"
import { HealthCheck } from "@/components/shared/HealthCheck"
import { API_ROUTES } from "@/lib/api/routes"
import type { Feedback } from "@/lib/api/types"
import { common } from "@/locales/en/common"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

export default function Home() {
  const handleCreated = async (newFeedback: Feedback) => {
    // Optimistic update: prepend the new row to the SWR cache without
    // refetching. The list re-renders immediately; the next focus-trigger
    // or page load revalidates from /api/v1/feedback.
    await mutate<Feedback[]>(
      API_ROUTES.feedback,
      (current) => (current ? [newFeedback, ...current] : [newFeedback]),
      { revalidate: false },
    )
  }

  return (
    <main className="container mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{common.app.title}</h1>
        <HealthCheck />
      </header>

      <PasteForm onCreated={handleCreated} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{feedbackCopy.list.title}</h2>
        <FeedbackList />
      </section>
    </main>
  )
}
