import { apiRequest } from "./client";

export interface HealthResponse {
  status: string;
}

export function getLiveness(signal?: AbortSignal) {
  return apiRequest<HealthResponse>("/health/live", { signal });
}

export function getReadiness(signal?: AbortSignal) {
  return apiRequest<HealthResponse>("/health/ready", { signal });
}
