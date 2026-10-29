import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({ user: { role: 'operator' } }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => auth }));

import { ReceiptsPage } from './ReceiptsPage';

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ReceiptsPage />
    </QueryClientProvider>,
  );
}

describe('ReceiptsPage', () => {
  it('проводит черновик только после подтверждения', async () => {
    const fetchMock = vi.fn((input: string, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/receipts/?'))
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: 'r1',
                  document_number: 'DOC-1',
                  received_at: '2026-01-01T12:00:00Z',
                  status: 'draft',
                  supplier_name: 'Поставщик',
                  items: [],
                },
              ],
              total: 1,
              skip: 0,
              limit: 20,
            }),
            { status: 200 },
          ),
        );
      if (init?.method === 'POST')
        return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(
        new Response(
          JSON.stringify({ items: [], total: 0, skip: 0, limit: 1000 }),
          { status: 200 },
        ),
      );
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal(
      'confirm',
      vi.fn(() => true),
    );
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Провести' }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/receipts/r1/post'),
        expect.anything(),
      ),
    );
  });

  it('открывает форму, показывает ошибочное количество и не отправляет его', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ items: [], total: 0, skip: 0, limit: 1000 }),
            { status: 200 },
          ),
        ),
      ),
    );
    renderPage();
    fireEvent.click(
      await screen.findByRole('button', { name: 'Создать поступление' }),
    );
    const quantity = await screen.findByLabelText('Количество');
    fireEvent.change(quantity, { target: { value: '1.2345' } });
    expect(
      screen.getByText(
        'Укажите положительное число не более чем с тремя знаками.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeDisabled();
  });
});
