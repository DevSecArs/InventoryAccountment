import { describe, expect, it, vi } from 'vitest';
import * as catalogs from './catalogs';
import * as receipts from './receipts';
import * as auth from './auth';

describe('Контракты API', () => {
  it('кодирует идентификаторы и фильтры справочников', async () => {
    const fetch = vi.fn(async () => Response.json({ items: [] }));
    vi.stubGlobal('fetch', fetch);
    await catalogs.listCatalog('units', {
      skip: 0,
      limit: 20,
      search: ' кг ',
      includeArchived: true,
    });
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining('search=%D0%BA%D0%B3'),
      expect.anything(),
    );
    await catalogs.listSiUnitOptions();
    await catalogs.createCatalog('units', { name: 'Кг' });
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/units/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Кг' }),
      }),
    );
    await catalogs.updateCatalog('units', 'a/b', { name: 'Грамм' });
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/units/a%2Fb',
      expect.objectContaining({ method: 'PUT' }),
    );
    await catalogs.archiveCatalog('units', 'a/b');
    await catalogs.purgeCatalog('units', 'a/b');
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/units/a%2Fb/purge',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('сохраняет методы операций поступлений и фильтры отчётного периода', async () => {
    const fetch = vi.fn(async () => Response.json({ items: [] }));
    vi.stubGlobal('fetch', fetch);
    await receipts.listReceipts({
      skip: 0,
      limit: 20,
      search: ' DOC ',
      supplierId: 's1',
      status: 'draft',
      from: '2026-01-01',
      to: '2026-02-01',
    });
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining(
        'supplier_id=s1&status=draft&search=DOC&from=2026-01-01&to=2026-02-01',
      ),
      expect.anything(),
    );
    await receipts.getReceipt('a/b');
    await receipts.createReceipt({
      supplier_id: 's1',
      document_number: 'DOC',
      received_at: '2026-01-01',
      items: [],
    });
    await receipts.updateReceipt('a/b', { document_number: 'NEW' });
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/receipts/a%2Fb',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ document_number: 'NEW' }),
      }),
    );
    await receipts.deleteReceipt('a/b');
    await receipts.postReceipt('a/b');
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/receipts/a%2Fb/post',
      expect.objectContaining({ method: 'POST' }),
    );
    await receipts.getReceiptHistory('a/b');
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/receipts/a%2Fb/history',
      expect.anything(),
    );
  });

  it('передаёт данные регистрации, входа и изменения профиля', async () => {
    const fetch = vi.fn(async () => Response.json({}));
    vi.stubGlobal('fetch', fetch);
    await auth.login({ login: 'user', password: 'secret' });
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ login: 'user', password: 'secret' }),
      }),
    );
    await auth.register({
      login: 'new',
      password: 'long-password',
      full_name: 'Имя',
    });
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/auth/register',
      expect.objectContaining({ method: 'POST' }),
    );
    await auth.updateProfile({ full_name: 'Новое имя', email: null });
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/auth/me',
      expect.objectContaining({ method: 'PUT' }),
    );
  });
});
