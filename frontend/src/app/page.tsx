import { StatsDashboard } from "@/components/stats/StatsDashboard"

export default function Home() {
  return (
    <main className="container mx-auto max-w-5xl px-4 py-8 flex flex-col gap-6">
      <StatsDashboard />
    </main>
  )
}
