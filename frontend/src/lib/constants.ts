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
  /** SWR refresh interval for the stats dashboard when pending_count > 0
   *  (active drain). 5s is the sweet spot during work: fast enough to feel
   *  live, slow enough not to hammer the DB. */
  statsDashboardRefreshMs: 5_000,
  /** SWR refresh interval for the stats dashboard when pending_count = 0
   *  (idle). 30s — dashboard still eventually fresh on background changes
   *  (beat-scheduled summary regen, another tab submitting) but doesn't
   *  burn ~14 req/min on an idle tab. Matches the conditional-SSE design:
   *  active state pays for snappy updates, idle state minimizes traffic. */
  statsDashboardIdleRefreshMs: 30_000,
  /** Debounce delay for the /feedback search input. 300ms is the standard
   *  sweet spot — fast enough to feel responsive, slow enough to coalesce
   *  bursts of keystrokes into one API request. */
  feedbackSearchDebounceMs: 300,
} as const

export const UI_DIMENSIONS = {
  /** Default visible rows for the paste textarea. */
  pasteFormRows: 6,
  /** Fixed height for the theme-frequency vertical bar chart container.
   *  Vertical layout means height is constant regardless of theme count;
   *  the chart inner div grows horizontally and scrolls inside the card. */
  themeChartHeightPx: 320,
  /** Y-axis ceiling for the theme-frequency chart. Counts above this clip
   *  rather than rescale, so the visual reference stays stable as data grows. */
  themeChartYAxisMax: 50,
  /** Tick spacing on the theme-frequency chart Y axis (0, 10, 20, …, max). */
  themeChartYAxisStep: 10,
  /** Minimum horizontal slot per theme bar. Total inner width = max(card,
   *  themes.length × this). Chart wrapper has overflow-x-auto, so beyond
   *  the card width the chart scrolls horizontally instead of cramming. */
  themeChartSlotMinPx: 60,
  /** XAxis bottom band height — large enough for long rotated labels
   *  like "android 14 compatibility" at -35° without clipping. */
  themeChartLabelHeightPx: 90,
  /** Width of the frozen YAxis sidecar chart on the theme-frequency view.
   *  See the dual-chart pattern in ThemeFrequencyChart for why this exists. */
  themeChartYAxisWidthPx: 44,
  /** Fixed height for the sentiment trend chart container. */
  sentimentTrendHeightPx: 280,
  /** Page size for the /feedback table. 20 fits a screen comfortably without
   *  forcing the user to scroll the whole page on a typical desktop. */
  feedbackPageSize: 20,
} as const

export const UI_FORMATTING = {
  /** Threshold (and divisor) for "k" formatting on token counts:
   *  values < threshold render as-is; values >= threshold render as `${n/k}k`. */
  tokensKThreshold: 1_000,
} as const
