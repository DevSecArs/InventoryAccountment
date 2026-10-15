import { apiRequest } from './client';
import type { Page } from './catalogs';

export interface ReceiptItemInput {
  material_id: string;
  quantity: string;
}
export interface ReceiptInput {
  supplier_id: string;
  document_number: string;
  received_at: string;
  items: ReceiptItemInput[];
}
export interface ReceiptItem extends ReceiptItemInput {
  id: string;
  material_sku?: string;
  material_name?: string;
  unit_id?: string;
  unit_code?: string;
  unit_name?: string;
}
export interface Receipt {
  id: string;
  supplier_id: string;
  supplier_name?: string;
  document_number: string;
  received_at: string;
  status: string;
  created_at: string;
  updated_at: string;
  items: ReceiptItem[];
}
export interface ReceiptFilters {
  skip: number;
  limit: number;
  supplierId?: string;
  status?: string;
  search?: string;
  from?: string;
  to?: string;
}
export interface ReceiptHistory {
  id: string;
  receipt_id: string;
  from_status: string;
  to_status: string;
  changed_at: string;
  reason?: string | null;
}

function query(filters: ReceiptFilters) {
  const params = new URLSearchParams({
    skip: String(filters.skip),
    limit: String(filters.limit),
  });
  if (filters.supplierId) params.set('supplier_id', filters.supplierId);
  if (filters.status) params.set('status', filters.status);
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  return params.toString();
}
export const listReceipts = (filters: ReceiptFilters, signal?: AbortSignal) =>
  apiRequest<Page<Receipt>>(`/api/v1/receipts/?${query(filters)}`, { signal });
export const getReceipt = (id: string) =>
  apiRequest<Receipt>(`/api/v1/receipts/${encodeURIComponent(id)}`);
export const createReceipt = (input: ReceiptInput) =>
  apiRequest<Receipt>('/api/v1/receipts/', {
    method: 'POST',
    body: JSON.stringify(input),
  });
export const updateReceipt = (id: string, input: Partial<ReceiptInput>) =>
  apiRequest<Receipt>(`/api/v1/receipts/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
export const deleteReceipt = (id: string) =>
  apiRequest<void>(`/api/v1/receipts/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
export const postReceipt = (id: string) =>
  apiRequest<Receipt>(`/api/v1/receipts/${encodeURIComponent(id)}/post`, {
    method: 'POST',
  });
export const getReceiptHistory = (id: string) =>
  apiRequest<{ items: ReceiptHistory[] }>(
    `/api/v1/receipts/${encodeURIComponent(id)}/history`,
  );
