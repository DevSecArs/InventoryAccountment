import { apiRequest } from './client.js';

export const getCurrentUser = () => apiRequest('/api/v1/auth/me');
export const login = (credentials, signal) => apiRequest('/api/v1/auth/login', { method: 'POST', signal, body: JSON.stringify(credentials) });
export const register = (payload, signal) => apiRequest('/api/v1/auth/register', { method: 'POST', signal, body: JSON.stringify(payload) });
export const logout = () => apiRequest('/api/v1/auth/logout', { method: 'POST' });
export const updateProfile = (payload, signal) => apiRequest('/api/v1/auth/me', { method: 'PUT', signal, body: JSON.stringify(payload) });
