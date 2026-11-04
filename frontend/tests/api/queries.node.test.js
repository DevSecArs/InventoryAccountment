import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { catalogQuery } from '../../src/api/catalogs.js';
import { receiptQuery } from '../../src/api/receipts.js';
import { reportQuery } from '../../src/api/reports.js';

test('фильтры справочника кодируют поиск и архив', () => {
  const p = new URLSearchParams(catalogQuery({ skip: 0, limit: 10, search: '  болт & гайка ', includeArchived: true }));
  assert.equal(p.get('search'), 'болт & гайка');
  assert.equal(p.get('include_archived'), 'true');
});
test('фильтры поступлений сохраняют поля API', () => {
  const p = new URLSearchParams(receiptQuery({ skip: 2, limit: 5, supplierId: 's', status: 'draft', search: ' x ', from: '2024-01-01', to: '2024-02-01' }));
  assert.equal(p.get('supplier_id'), 's');
  assert.equal(p.get('search'), 'x');
  assert.equal(p.get('status'), 'draft');
  assert.equal(p.get('from'), '2024-01-01');
  assert.equal(p.get('to'), '2024-02-01');
});
test('фильтры отчёта сохраняют нулевую страницу', () => {
  const p = new URLSearchParams(reportQuery({ from: 'a', to: 'b', supplierId: 's', materialId: 'm', skip: 0, limit: 10 }));
  assert.equal(p.get('skip'), '0');
  assert.equal(p.get('material_id'), 'm');
  assert.equal(p.get('supplier_id'), 's');
});
