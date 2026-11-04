import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readReportFilters, updateReportQuery } from '../../src/native/report-logic.js';

test('параметры отчёта восстанавливаются из URL и проверяют страницу', () => {
  assert.deepEqual(readReportFilters('?from=a&to=b&supplier_id=s&material_id=m&skip=50'), { from: 'a', to: 'b', supplierId: 's', materialId: 'm', skip: 50, limit: 50 });
  for (const skip of ['-1', '1.5', 'Infinity', 'bad']) assert.equal(readReportFilters(`?skip=${skip}`).skip, 0);
  assert.equal(readReportFilters('').from, '');
});
test('изменение фильтра сохраняет период и сбрасывает пагинацию', () => {
  const query = updateReportQuery('?from=a&to=b&skip=50', 'supplier_id', 's');
  const params = new URLSearchParams(query);
  assert.equal(params.get('from'), 'a'); assert.equal(params.get('to'), 'b');
  assert.equal(params.get('supplier_id'), 's'); assert.equal(params.get('skip'), '0');
  assert.equal(new URLSearchParams(updateReportQuery(query, 'supplier_id', '')).has('supplier_id'), false);
  assert.equal(new URLSearchParams(updateReportQuery(query, 'skip', '50')).get('skip'), '50');
});
