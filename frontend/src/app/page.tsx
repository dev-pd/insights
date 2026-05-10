import { HealthCheck } from "@/components/HealthCheck"

export default function HomePage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold mb-2">Feedback Insights</h1>
        <p className="text-gray-600 mb-4">
          LLM-powered customer feedback extraction and analytics
        </p>
        <HealthCheck />
      </header>

      <section className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-medium mb-2">Phase 1: plumbing</h2>
        <p className="text-gray-600 text-sm">
          Real features arrive in subsequent phases: paste form and extraction in Phase 2,
          dashboard stats in Phase 3, async extraction with live updates in Phase 4.
        </p>
      </section>
    </main>
  )
}
