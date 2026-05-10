"use client"

import { mutate } from "swr"

import { FeedbackList } from "@/components/feedback/FeedbackList"
import { PasteForm } from "@/components/feedback/PasteForm"
import { HealthCheck } from "@/components/shared/HealthCheck"
import { StatsDashboard } from "@/components/stats/StatsDashboard"
import { API_ROUTES } from "@/lib/api/routes"
import type { Feedback } from "@/lib/api/types"
import { common } from "@/locales/en/common"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

export default function Home() {
  const handleCreated = async (newFeedback: Feedback) => {
    // Optimistic update: prepend the new row to the SWR cache so it
    // shows up before any revalidation.
    await mutate<Feedback[]>(
      API_ROUTES.feedback,
      (current) => (current ? [newFeedback, ...current] : [newFeedback]),
      { revalidate: false },
    )

    // Invalidate stats so the dashboard reflects the new row on next refresh
    // (or sooner via SWR's automatic revalidation).
    await mutate(API_ROUTES.stats)
  }

  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-8">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{common.app.title}</h1>
        <HealthCheck />
      </header>

      <StatsDashboard />

      <PasteForm onCreated={handleCreated} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{feedbackCopy.list.title}</h2>
        <FeedbackList />
      </section>
    </main>
  )
}
