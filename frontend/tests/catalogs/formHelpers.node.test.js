import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { nullable, formatDate } from '../../src/features/catalogs/formHelpers.js';

test('nullable нормализует пустые и непустые значения', () => {
  assert.equal(nullable('  '), null);
  assert.equal(nullable(' текст  '), 'текст');
});

test('formatDate обрабатывает отсутствие даты и форматирует дату', () => {
  assert.equal(formatDate(null), '—');
  const date = '2024-01-02T12:00:00Z';
  assert.equal(formatDate(date), new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(date)));
});
