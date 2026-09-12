import { apiRequest } from "./client";

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface CatalogListParams {
  skip: number;
  limit: number;
  search?: string;
  includeArchived?: boolean;
}

export interface CatalogRecord {
  id: string;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Unit extends CatalogRecord {
  code: string;
  name: string;
}

export interface UnitInput {
  code: string;
  name: string;
}

export interface Material extends CatalogRecord {
  sku: string;
  name: string;
  description: string | null;
  unit_id: string;
}

export interface MaterialInput {
  sku: string;
  name: string;
  description?: string | null;
  unit_id: string;
}

export interface Supplier extends CatalogRecord {
  code: string;
  name: string;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
}

export interface SupplierInput {
  code: string;
  name: string;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
}

export type CatalogResource = "units" | "materials" | "suppliers";

function queryString(params: CatalogListParams) {
  const query = new URLSearchParams({
    skip: String(params.skip),
    limit: String(params.limit),
    include_archived: String(params.includeArchived ?? false),
  });
  if (params.search?.trim()) {
    query.set("search", params.search.trim());
  }
  return query.toString();
}

export function listCatalog<T>(resource: CatalogResource, params: CatalogListParams, signal?: AbortSignal) {
  return apiRequest<Page<T>>(`/api/v1/${resource}/?${queryString(params)}`, { signal });
}

export function createCatalog<T, TInput>(resource: CatalogResource, input: TInput) {
  return apiRequest<T>(`/api/v1/${resource}/`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateCatalog<T, TInput>(resource: CatalogResource, id: string, input: Partial<TInput>) {
  return apiRequest<T>(`/api/v1/${resource}/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function archiveCatalog(resource: CatalogResource, id: string) {
  return apiRequest<void>(`/api/v1/${resource}/${encodeURIComponent(id)}`, { method: "DELETE" });
}
