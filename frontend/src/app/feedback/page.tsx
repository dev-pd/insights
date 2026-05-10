"use client"

import { FeedbackList } from "@/components/feedback/FeedbackList"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

export default function FeedbackPage() {
  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{feedbackCopy.list.title}</h1>
      </header>

      <FeedbackList />
    </main>
  )
}
