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
