import { apiBlobRequest, apiRequest } from './client';

export interface ReportFilters {
  from: string;
  to: string;
  supplierId?: string;
  materialId?: string;
  skip?: number;
  limit?: number;
}
export interface SupplyRow {
  receipt_id: string;
  document_number: string;
  received_at: string;
  supplier_id: string;
  supplier_name: string;
  material_id: string;
  material_sku: string;
  material_name: string;
  unit_id: string;
  unit_code: string;
  unit_name: string;
  quantity: string;
}
export interface SupplyReport {
  items: SupplyRow[];
  total: number;
  skip: number;
  limit: number;
  totals: Omit<
    SupplyRow,
    | 'receipt_id'
    | 'document_number'
    | 'received_at'
    | 'supplier_id'
    | 'supplier_name'
  >[];
}
function query(filters: ReportFilters) {
  const params = new URLSearchParams({ from: filters.from, to: filters.to });
  if (filters.supplierId) params.set('supplier_id', filters.supplierId);
  if (filters.materialId) params.set('material_id', filters.materialId);
  if (filters.skip !== undefined) params.set('skip', String(filters.skip));
  if (filters.limit !== undefined) params.set('limit', String(filters.limit));
  return params.toString();
}
export const getSupplyReport = (filters: ReportFilters, signal?: AbortSignal) =>
  apiRequest<SupplyReport>(`/api/v1/reports/supplies?${query(filters)}`, {
    signal,
  });
export const exportSupplyReport = (filters: ReportFilters) =>
  apiBlobRequest(`/api/v1/reports/supplies/export?${query(filters)}`);
