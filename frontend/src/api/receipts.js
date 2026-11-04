import { apiRequest } from './client.js';

export function receiptQuery(filters) {
  const params = new URLSearchParams({ skip: String(filters.skip), limit: String(filters.limit) });
  if (filters.supplierId) params.set('supplier_id', filters.supplierId);
  if (filters.status) params.set('status', filters.status);
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  return params.toString();
}
export const listReceipts = (filters, signal) => apiRequest(`/api/v1/receipts/?${receiptQuery(filters)}`, { signal });
export const getReceipt = (id, signal) => apiRequest(`/api/v1/receipts/${encodeURIComponent(id)}`, { signal });
export const createReceipt = (input, signal) => apiRequest('/api/v1/receipts/', { method: 'POST', signal, body: JSON.stringify(input) });
export const updateReceipt = (id, input, signal) => apiRequest(`/api/v1/receipts/${encodeURIComponent(id)}`, { method: 'PATCH', signal, body: JSON.stringify(input) });
export const deleteReceipt = (id, signal) => apiRequest(`/api/v1/receipts/${encodeURIComponent(id)}`, { method: 'DELETE', signal });
export const postReceipt = (id, signal) => apiRequest(`/api/v1/receipts/${encodeURIComponent(id)}/post`, { method: 'POST', signal });
export const getReceiptHistory = (id, signal) => apiRequest(`/api/v1/receipts/${encodeURIComponent(id)}/history`, { signal });
