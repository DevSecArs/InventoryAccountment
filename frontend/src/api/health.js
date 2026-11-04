import { apiRequest } from './client.js';
export const getLiveness = signal => apiRequest('/health/live', { signal });
export const getReadiness = signal => apiRequest('/health/ready', { signal });
