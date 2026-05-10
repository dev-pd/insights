"use client"

import { mutate } from "swr"

import { PasteForm } from "@/components/feedback/PasteForm"
import { API_ROUTES } from "@/lib/api/routes"
import type { Feedback } from "@/lib/api/types"
import { addFeedback } from "@/locales/en/addFeedback"

export default function AddFeedbackPage() {
  const handleCreated = async (newFeedback: Feedback) => {
    // Optimistically prepend to the feedback list cache so the row is there
    // when the user navigates to /feedback. Stats gets a plain mutate to
    // force a refetch since we'd compute aggregates wrong locally.
    await mutate<Feedback[]>(
      API_ROUTES.feedback,
      (current) => (current ? [newFeedback, ...current] : [newFeedback]),
      { revalidate: false },
    )
    await mutate(API_ROUTES.stats)
  }

  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold">{addFeedback.page.title}</h1>
        <p className="text-sm text-muted-foreground">
          {addFeedback.page.description}
        </p>
      </header>

      <div className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 px-4 py-3">
        <p className="text-sm text-amber-900 dark:text-amber-200">
          {addFeedback.page.bulkUploadNote}
        </p>
      </div>

      <PasteForm onCreated={handleCreated} />
    </main>
  )
}
