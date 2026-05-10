/**
 * Centralized UI constants. Per the frontend conventions: no magic numbers
 * inline in components — anything that could vary, repeat, or be tuned per
 * environment lives here.
 *
 * Backend tunables (timeouts, validation thresholds, page sizes) live in
 * backend Settings / backend/.env.example, not here. This file is for
 * UI-only values: client-side polling, animation, and component dimensions.
 */

export const UI_TIMINGS = {
  /** AbortController timeout for any apiClient request. */
  apiRequestTimeoutMs: 30_000,
  /** SWR refresh interval for the /api/health pill (live backend status). */
  healthCheckRefreshMs: 30_000,
  /** SWR refresh interval for the feedback list. 0 = no automatic polling
   *  (Phase 2 is synchronous; Phase 4 will replace polling with SSE). */
  feedbackListRefreshMs: 0,
} as const

export const UI_DIMENSIONS = {
  /** Default visible rows for the paste textarea. */
  pasteFormRows: 6,
} as const
