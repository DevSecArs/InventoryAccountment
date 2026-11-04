import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { statusLabel, canWriteReceipts, receiptInput } from '../../src/native/receipt-logic.js';

test('роли и статусы поступлений соответствуют текущему интерфейсу', () => {
  assert.equal(canWriteReceipts('admin'), true); assert.equal(canWriteReceipts('operator'), true);
  assert.equal(canWriteReceipts('reporter'), false);
  assert.equal(statusLabel('draft'), 'Черновик'); assert.equal(statusLabel('posted'), 'Проведено'); assert.equal(statusLabel('other'), 'other');
});
test('поступление сохраняет десятичную строку и переводит локальную дату в ISO', () => {
  const input = { supplier_id: 's', document_number: 'DOC', received_at: '2026-01-01T12:00', material_id: 'm', quantity: '0.100' };
  assert.deepEqual(receiptInput(input), { supplier_id: 's', document_number: 'DOC', received_at: new Date(input.received_at).toISOString(), items: [{ material_id: 'm', quantity: '0.100' }] });
  for (const change of [{ supplier_id: '' }, { material_id: '' }, { document_number: ' ' }, { quantity: '0.000' }, { quantity: '1.2345' }, { received_at: '' }, { received_at: 'bad' }]) assert.throws(() => receiptInput({ ...input, ...change }));
});
