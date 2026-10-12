import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ReportsPage } from './ReportsPage';

function renderPage(entry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes><Route path="/reports" element={<ReportsPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('ReportsPage', () => {
  it('не запрашивает отчёт, пока период не выбран', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderPage('/reports');
    expect(screen.getByText('Укажите начало и конец периода.')).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls.map(([url]) => String(url))).not.toContain('/api/v1/reports/supplies');
  });

  it('отображает серверные строки и точные итоги', async () => {
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      const url = String(input);
      if (url.includes('/reports/supplies?')) {
        return Promise.resolve(new Response(JSON.stringify({ items: [{ receipt_id: 'r1', document_number: 'DOC-1', received_at: '2026-01-01T12:00:00Z', supplier_id: 's1', supplier_name: 'Поставщик', material_id: 'm1', material_sku: 'MAT', material_name: 'Материал', unit_id: 'u1', unit_code: 'KG', unit_name: 'Килограмм', quantity: '0.100' }], total: 1, skip: 0, limit: 50, totals: [{ material_id: 'm1', material_sku: 'MAT', material_name: 'Материал', unit_id: 'u1', unit_code: 'KG', unit_name: 'Килограмм', quantity: '0.100' }] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0, skip: 0, limit: 1000 }), { status: 200 }));
    }));
    renderPage('/reports?from=2026-01-01T00%3A00%3A00.000Z&to=2026-01-02T00%3A00%3A00.000Z');
    expect(await screen.findByText('DOC-1')).toBeInTheDocument();
    expect(screen.getAllByText(/0\.100 KG/)).not.toHaveLength(0);
    expect(screen.getByText('Всего строк: 1')).toBeInTheDocument();
  });
});
