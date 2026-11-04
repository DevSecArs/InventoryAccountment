import { test, afterEach, mock } from 'node:test';
import { strict as assert } from 'node:assert';
import * as catalogs from '../../src/api/catalogs.js';
import * as receipts from '../../src/api/receipts.js';
import * as auth from '../../src/api/auth.js';
import * as health from '../../src/api/health.js';
import { getSupplyReport, exportSupplyReport } from '../../src/api/reports.js';

afterEach(() => mock.restoreAll());
test('контракты справочников сохраняют методы и кодирование идентификаторов', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({ items: [] }));
  const check = (path, method = 'GET', body) => { const [url, init] = fetchMock.mock.calls.at(-1).arguments; assert.equal(url, path); assert.equal(init.method ?? 'GET', method); if (body) assert.deepEqual(JSON.parse(init.body), body); };
  await catalogs.listCatalog('units', { skip: 0, limit: 20, search: ' кг ', includeArchived: true });
  assert.match(fetchMock.mock.calls.at(-1).arguments[0], /search=%D0%BA%D0%B3/);
  await catalogs.listSiUnitOptions(); check('/api/v1/units/si-options');
  await catalogs.createCatalog('units', { name: 'Кг' }); check('/api/v1/units/', 'POST', { name: 'Кг' });
  await catalogs.updateCatalog('units', 'a/b', { name: 'Грамм' }); check('/api/v1/units/a%2Fb', 'PUT', { name: 'Грамм' });
  await catalogs.archiveCatalog('units', 'a/b'); check('/api/v1/units/a%2Fb', 'DELETE');
  await catalogs.purgeCatalog('units', 'a/b'); check('/api/v1/units/a%2Fb/purge', 'DELETE');
});
test('контракты документов и авторизации сохраняют методы и тело', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({ items: [] }));
  const check = (path, method = 'GET') => { const [url, init] = fetchMock.mock.calls.at(-1).arguments; assert.equal(url, path); assert.equal(init.method ?? 'GET', method); };
  await receipts.getReceipt('a/b'); check('/api/v1/receipts/a%2Fb');
  await receipts.createReceipt({ items: [] }); check('/api/v1/receipts/', 'POST');
  await receipts.updateReceipt('a/b', { document_number: 'NEW' }); check('/api/v1/receipts/a%2Fb', 'PATCH');
  assert.deepEqual(JSON.parse(fetchMock.mock.calls.at(-1).arguments[1].body), { document_number: 'NEW' });
  await receipts.deleteReceipt('a/b'); check('/api/v1/receipts/a%2Fb', 'DELETE');
  await receipts.postReceipt('a/b'); check('/api/v1/receipts/a%2Fb/post', 'POST');
  await receipts.getReceiptHistory('a/b'); check('/api/v1/receipts/a%2Fb/history');
  await auth.getCurrentUser(); check('/api/v1/auth/me');
  await auth.login({ login: 'user', password: 'secret' }); check('/api/v1/auth/login', 'POST');
  await auth.register({ login: 'new', password: 'long-password', full_name: 'Имя' }); check('/api/v1/auth/register', 'POST');
  await auth.updateProfile({ full_name: 'Имя', email: null }); check('/api/v1/auth/me', 'PUT');
  await auth.logout(); check('/api/v1/auth/logout', 'POST');
  await health.getLiveness(); check('/health/live'); await health.getReadiness(); check('/health/ready');
  await getSupplyReport({ from: 'a', to: 'b' }); assert.match(fetchMock.mock.calls.at(-1).arguments[0], /^\/api\/v1\/reports\/supplies\?/);
  await exportSupplyReport({ from: 'a', to: 'b' }); assert.match(fetchMock.mock.calls.at(-1).arguments[0], /^\/api\/v1\/reports\/supplies\/export\?/);
});

test('список поступлений передаёт фильтры и сигнал отмены', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({ items: [], total: 0 }));
  const controller = new AbortController();
  await receipts.listReceipts({ skip: 20, limit: 20, supplierId: 's', status: 'draft', search: ' DOC ', from: 'a', to: 'b' }, controller.signal);
  const [url, options] = fetchMock.mock.calls[0].arguments;
  const query = new URL(url, 'http://localhost').searchParams;
  assert.equal(query.get('supplier_id'), 's');
  assert.equal(query.get('status'), 'draft');
  assert.equal(query.get('search'), 'DOC');
  assert.equal(query.get('from'), 'a');
  assert.equal(query.get('to'), 'b');
  assert.equal(options.signal, controller.signal);
});
