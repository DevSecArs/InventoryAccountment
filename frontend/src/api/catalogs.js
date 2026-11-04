import { apiRequest } from './client.js';

export function catalogQuery(params) {
  const query = new URLSearchParams({ skip: String(params.skip), limit: String(params.limit), include_archived: String(params.includeArchived ?? false) });
  if (params.search?.trim()) query.set('search', params.search.trim());
  return query.toString();
}
export const listCatalog = (resource, params, signal) => apiRequest(`/api/v1/${resource}/?${catalogQuery(params)}`, { signal });
export const listSiUnitOptions = signal => apiRequest('/api/v1/units/si-options', { signal });
export const createCatalog = (resource, input, signal) => apiRequest(`/api/v1/${resource}/`, { method: 'POST', signal, body: JSON.stringify(input) });
export const updateCatalog = (resource, id, input, signal) => apiRequest(`/api/v1/${resource}/${encodeURIComponent(id)}`, { method: 'PUT', signal, body: JSON.stringify(input) });
export const archiveCatalog = (resource, id, signal) => apiRequest(`/api/v1/${resource}/${encodeURIComponent(id)}`, { method: 'DELETE', signal });
export const purgeCatalog = (resource, id, signal) => apiRequest(`/api/v1/${resource}/${encodeURIComponent(id)}/purge`, { method: 'DELETE', signal });
