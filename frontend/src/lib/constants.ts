/**
 * Centralized UI constants. Per the frontend conventions: no magic numbers
 * inline in components — anything that could vary, repeat, or be tuned per
 * environment lives here.
 *
 * Backend tunables (timeouts, validation thresholds, page sizes, top-N
 * limits) live in backend Settings / backend/.env.example, not here. This
 * file is for UI-only values: client-side polling, animation, dimensions,
 * and display formatting thresholds.
 */

export const UI_TIMINGS = {
  /** AbortController timeout for any apiClient request. */
  apiRequestTimeoutMs: 30_000,
  /** SWR refresh interval for the /api/health pill (live backend status). */
  healthCheckRefreshMs: 30_000,
  /** SWR refresh interval for the feedback list. 0 = no automatic polling
   *  (Phase 2 is synchronous; Phase 4 will replace polling with SSE). */
  feedbackListRefreshMs: 0,
  /** SWR refresh interval for the stats dashboard. 5s is the sweet spot:
   *  fast enough to feel live, slow enough not to hammer the DB. */
  statsDashboardRefreshMs: 5_000,
} as const

export const UI_DIMENSIONS = {
  /** Default visible rows for the paste textarea. */
  pasteFormRows: 6,
  /** Pixel height per row in the theme-frequency horizontal bar chart. */
  themeChartRowHeightPx: 36,
  /** Minimum height for the theme-frequency chart container. */
  themeChartMinHeightPx: 200,
  /** Fixed height for the sentiment trend chart container. */
  sentimentTrendHeightPx: 280,
} as const

export const UI_FORMATTING = {
  /** Threshold (and divisor) for "k" formatting on token counts:
   *  values < threshold render as-is; values >= threshold render as `${n/k}k`. */
  tokensKThreshold: 1_000,
} as const
