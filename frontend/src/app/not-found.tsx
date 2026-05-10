import Link from "next/link"

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8">
      <h2 className="text-2xl font-semibold mb-4">Page not found</h2>
      <Link href="/" className="text-blue-600 hover:underline">
        Go home
      </Link>
    </div>
  )
}
