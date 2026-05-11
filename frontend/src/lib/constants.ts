// UI-only values. Backend tunables (timeouts, limits) live in backend Settings.

export const UI_TIMINGS = {
  apiRequestTimeoutMs: 30_000,
  healthCheckRefreshMs: 30_000,
  feedbackListRefreshMs: 0,
  // 5s when pending_count > 0, 30s when idle — see useDashboardStats.
  statsDashboardRefreshMs: 5_000,
  statsDashboardIdleRefreshMs: 30_000,
  // Adaptive poll for SummaryWidget. 3s during active burst (pending > 0)
  // because the placeholder "0 extracted" sentinel can be served at T=0
  // before any items finish, and the user needs to see real summary text
  // as the threshold is crossed. 60s idle — cheap Redis cache hits only.
  // SSE-driven summary_invalidate is the primary signal, but SSE closes
  // when pending_count==0 so this poll is the belt-and-suspenders fallback.
  summaryActiveRefreshMs: 3_000,
  summaryIdleRefreshMs: 60_000,
  feedbackSearchDebounceMs: 300,
} as const

export const UI_DIMENSIONS = {
  pasteFormRows: 6,
  themeChartHeightPx: 320,
  // Pinned Y axis: counts above clip rather than rescale (stable reference as data grows).
  themeChartYAxisMax: 50,
  themeChartYAxisStep: 10,
  // Bars min-width × count → total inner width; chart scrolls horizontally past card.
  themeChartSlotMinPx: 60,
  // Reserves space for -35° rotated labels (e.g. "android 14 compatibility").
  themeChartLabelHeightPx: 90,
  // Sidecar frozen YAxis — see dual-chart pattern in ThemeFrequencyChart.
  themeChartYAxisWidthPx: 44,
  sentimentTrendHeightPx: 280,
  feedbackPageSize: 10,
} as const
