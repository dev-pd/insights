"use client"

import { common } from "@/locales/en/common"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8">
      <h2 className="text-2xl font-semibold mb-4">{common.errors.generic}</h2>
      <p className="text-gray-600 mb-6">{error.message}</p>
      <button
        onClick={reset}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        {common.actions.tryAgain}
      </button>
    </div>
  )
}
