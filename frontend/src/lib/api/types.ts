export interface HealthResponse {
  status: string
}

export interface ReadyResponse {
  status: string
  database: boolean
  redis: boolean
}

export interface ApiError {
  error: string
  message: string
  request_id: string
}

export type Sentiment = "positive" | "neutral" | "negative"

export type FeedbackStatus = "processing" | "extracted" | "skipped" | "failed"

export type SkipReason =
  | "empty"
  | "too_short"
  | "too_long"
  | "gibberish"
  | "profanity"
  | "llm_validation_error"

export interface LlmMetadata {
  model?: string
  latency_ms?: number
  input_tokens?: number
  output_tokens?: number
  prompt_version?: string
  error_type?: string
  error?: string
}

export interface Feedback {
  id: number
  text: string
  status: FeedbackStatus
  sentiment: Sentiment | null
  themes: string[]
  action_items: string[]
  language: string | null
  skip_reason: SkipReason | null
  llm_metadata: LlmMetadata | null
  created_at: string
  updated_at: string | null
}

export interface FeedbackCreateRequest {
  text: string
}

export interface FeedbackPaginatedResponse {
  items: Feedback[]
  /** Total feedback matching the active filter, not just this page. */
  total: number
  offset: number
  limit: number
}

export interface FeedbackBatchRequest {
  texts: string[]
}

export interface FeedbackBatchResponse {
  items: Feedback[]
  total: number
  extracted: number
  skipped: number
  failed: number
}

export interface Summary {
  text: string
  /** ISO 8601 UTC timestamp. */
  generated_at: string
  feedback_count: number
  /** True if returned from Redis cache, false if freshly generated. */
  cached: boolean
  /** Set when LLM generation failed; failures are NOT cached server-side. */
  error?: string | null
  /** LLM call metadata. Null on the "not enough data" path and on errors. */
  metadata?: Record<string, unknown> | null
}

export interface ThemeCount {
  theme: string
  count: number
}

export interface SentimentBreakdown {
  positive: number
  neutral: number
  negative: number
}

export interface SentimentTrendPoint {
  /** ISO date string for the time bucket (YYYY-MM-DD). */
  bucket: string
  positive: number
  neutral: number
  negative: number
}

export interface WeeklyDelta {
  this_week_count: number
  last_week_count: number
  /** Percent change vs last week. `null` when last week was zero — UI renders "-". */
  delta_pct: number | null
}

export interface Stats {
  total_feedback: number
  total_extracted: number
  total_skipped: number
  total_failed: number
  /** Phase 4: feedback rows currently in PROCESSING status (being handled by a Celery worker). */
  pending_count: number
  sentiment_breakdown: SentimentBreakdown
  positive_pct: number
  negative_pct: number
  weekly_delta: WeeklyDelta
  top_themes: ThemeCount[]
  sentiment_trend: SentimentTrendPoint[]
  avg_latency_ms: number | null
  total_input_tokens: number
  total_output_tokens: number
}
