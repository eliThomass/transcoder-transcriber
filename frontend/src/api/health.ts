import { API_ROUTES } from '../config/api.ts'
import { apiFetch } from './client.ts'
import type { HealthResponse } from './types.ts'

// Not used by the UI yet. Handy for checking the API is reachable, and the
// same endpoint can back a load balancer health check.
export function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>(API_ROUTES.health)
}
