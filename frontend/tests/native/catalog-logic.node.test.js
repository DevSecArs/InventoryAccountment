import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { catalogInput, catalogCells, pagination } from '../../src/native/catalog-logic.js';

test('создание единицы использует выбранную запись СИ', () => {
  assert.deepEqual(catalogInput('units', { code: ' KG ' }, false, [{ code: 'KG', name: 'Килограмм' }]), { code: 'KG', name: 'Килограмм' });
  assert.throws(() => catalogInput('units', { code: 'NO' }, false, []), /обязательные/);
  assert.deepEqual(catalogInput('units', { code: ' X ', name: ' Имя ' }, true, []), { code: 'X', name: 'Имя' });
});
test('пустые дополнительные реквизиты сохраняются как null', () => {
  assert.deepEqual(catalogInput('materials', { sku: ' A ', name: ' Материал ', unit_id: 'u', description: ' ' }, false, []), { sku: 'A', name: 'Материал', unit_id: 'u', description: null });
  assert.deepEqual(catalogInput('suppliers', { code: ' S ', name: ' Имя ', contact_person: '', phone: ' 123 ', email: '', address: '' }, false, []), { code: 'S', name: 'Имя', contact_person: null, phone: '123', email: null, address: null });
  assert.throws(() => catalogInput('suppliers', { code: ' ', name: 'Имя', contact_person: '', phone: '', email: '', address: '' }, false, []), /обязательные/);
});
test('таблица показывает имя единицы, архив и пустые контакты', () => {
  const item = { sku: 'X', name: 'Материал', unit_id: 'u', updated_at: null, archived_at: null };
  assert.deepEqual(catalogCells('materials', item, [{ id: 'u', name: 'Килограмм' }]), ['X', 'Материал', 'Килограмм', '—', 'Активен']);
  assert.equal(catalogCells('materials', item, [])[2], 'u');
  assert.deepEqual(catalogCells('units', { code: 'KG', name: 'Килограмм', updated_at: null, archived_at: 'now' }, []), ['KG', 'Килограмм', '—', 'В архиве']);
  assert.deepEqual(catalogCells('suppliers', { code: 'S', name: 'Поставщик', updated_at: null }, []), ['S', 'Поставщик', '—', '—', '—', 'Активен']);
});
test('границы страниц учитывают пустой и последний результат', () => {
  assert.deepEqual(pagination(0, 20, 0), { from: 0, to: 0, previous: 0, hasNext: false });
  assert.deepEqual(pagination(20, 20, 25), { from: 21, to: 25, previous: 0, hasNext: false });
  assert.equal(pagination(0, 20, 25).hasNext, true);
});
