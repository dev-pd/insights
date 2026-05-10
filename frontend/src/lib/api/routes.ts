export const API_ROUTES = {
  // Operational endpoints (unversioned, mounted at root on backend, /api/* via nginx)
  health: "/api/health",
  ready: "/api/ready",
  // Versioned API
  feedback: "/api/v1/feedback",
  feedbackBatch: "/api/v1/feedback/batch",
  feedbackPaginated: "/api/v1/feedback/paginated",
  stats: "/api/v1/stats",
  summary: "/api/v1/summary",
  summaryRefresh: "/api/v1/summary/refresh",
} as const
