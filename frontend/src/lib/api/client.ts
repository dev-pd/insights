import { UI_TIMINGS } from "@/lib/constants"

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || ""

export class ApiError extends Error {
  constructor(
    public status: number,
    public errorCode: string,
    message: string,
    public requestId?: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(
    () => controller.abort(),
    UI_TIMINGS.apiRequestTimeoutMs,
  )

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new ApiError(
        response.status,
        body.error || "UnknownError",
        body.message || response.statusText,
        body.request_id,
      )
    }

    return response.json()
  } finally {
    clearTimeout(timeout)
  }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
}

export const fetcher = <T>(url: string): Promise<T> => apiClient.get<T>(url)
