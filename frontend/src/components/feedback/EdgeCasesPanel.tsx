import { addFeedback } from "@/locales/en/addFeedback"

export function EdgeCasesPanel() {
  return (
    <section className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 px-4 py-4">
      <h2 className="text-sm font-semibold text-amber-900 dark:text-amber-200 mb-2">
        {addFeedback.edgeCases.title}
      </h2>
      <p className="text-xs text-amber-800 dark:text-amber-300/80 mb-3">
        {addFeedback.edgeCases.intro}
      </p>
      <ul className="flex flex-col gap-3">
        {addFeedback.edgeCases.cases.map((edgeCase) => (
          <li
            key={edgeCase.label}
            className="text-sm text-amber-900 dark:text-amber-200"
          >
            <div className="font-medium">{edgeCase.label}</div>
            <code className="block text-xs bg-amber-100/60 dark:bg-amber-900/40 rounded px-2 py-1 my-1 text-amber-950 dark:text-amber-100 font-mono">
              {edgeCase.text}
            </code>
            <p className="text-xs text-amber-800 dark:text-amber-300/80">
              → {edgeCase.expectation}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
