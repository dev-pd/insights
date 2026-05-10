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
