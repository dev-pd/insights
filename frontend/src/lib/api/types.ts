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

export interface Stats {
  total_feedback: number
  total_extracted: number
  total_skipped: number
  total_failed: number
  sentiment_breakdown: SentimentBreakdown
  top_themes: ThemeCount[]
  sentiment_trend: SentimentTrendPoint[]
  avg_latency_ms: number | null
  total_input_tokens: number
  total_output_tokens: number
}
