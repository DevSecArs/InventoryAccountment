import { apiBlobRequest, apiRequest } from './client.js';

export function reportQuery(filters) {
  const params = new URLSearchParams({ from: filters.from, to: filters.to });
  if (filters.supplierId) params.set('supplier_id', filters.supplierId);
  if (filters.materialId) params.set('material_id', filters.materialId);
  if (filters.skip !== undefined) params.set('skip', String(filters.skip));
  if (filters.limit !== undefined) params.set('limit', String(filters.limit));
  return params.toString();
}
export const getSupplyReport = (filters, signal) => apiRequest(`/api/v1/reports/supplies?${reportQuery(filters)}`, { signal });
export const exportSupplyReport = (filters, signal) => apiBlobRequest(`/api/v1/reports/supplies/export?${reportQuery(filters)}`, { signal });
