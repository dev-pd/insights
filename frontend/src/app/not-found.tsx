import Link from "next/link"

import { common } from "@/locales/en/common"

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8">
      <h2 className="text-2xl font-semibold mb-4">{common.errors.notFound}</h2>
      <Link href="/" className="text-blue-600 hover:underline">
        {common.actions.goHome}
      </Link>
    </div>
  )
}
