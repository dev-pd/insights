import { addFeedback } from "@/locales/en/addFeedback"

export function EdgeCasesPanel() {
  return (
    <section className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 px-4 py-4">
      <h2 className="text-sm font-semibold text-amber-900 dark:text-amber-200 mb-3">
        {addFeedback.edgeCases.title}
      </h2>
      <ul className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-2">
        {addFeedback.edgeCases.cases.map((edgeCase) => (
          <li key={edgeCase.label} className="text-sm">
            <span className="font-medium text-amber-900 dark:text-amber-200">
              {edgeCase.label}:
            </span>{" "}
            <code className="text-xs bg-amber-100/60 dark:bg-amber-900/40 rounded px-1.5 py-0.5 text-amber-950 dark:text-amber-100 font-mono">
              {edgeCase.text}
            </code>
          </li>
        ))}
      </ul>
    </section>
  )
}
