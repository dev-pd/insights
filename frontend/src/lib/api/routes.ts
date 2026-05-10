export const API_ROUTES = {
  // Operational endpoints (unversioned, mounted at root on backend, /api/* via nginx)
  health: "/api/health",
  ready: "/api/ready",
  // Versioned API
  feedback: "/api/v1/feedback",
} as const
