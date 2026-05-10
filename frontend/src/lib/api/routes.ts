export const API_ROUTES = {
  // Operational endpoints (unversioned, mounted at root on backend, /api/* via nginx)
  health: "/api/health",
  ready: "/api/ready",
  // Versioned API endpoints will follow /api/v1/ pattern, added in later phases
} as const
