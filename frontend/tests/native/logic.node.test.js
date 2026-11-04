import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { credentialErrors, profileInput } from '../../src/native/auth.js';
import { validQuantity } from '../../src/native/receipt-logic.js';
import { localDateTime } from '../../src/native/reports.js';

test('количество сохраняется строкой и допускает до трёх десятичных знаков', () => {
  for (const value of ['1', '0.001', '1.250']) assert.equal(validQuantity(value), true, value);
  for (const value of ['', '-1', '1,2', '1.2345', '0', '0.000']) assert.equal(validQuantity(value), false, value);
});
test('некорректные и пустые даты не попадают в локальное поле', () => {
  assert.equal(localDateTime(''), ''); assert.equal(localDateTime('bad'), '');
  assert.match(localDateTime('2026-01-01T12:00:00Z'), /^2026-01-01T\d\d:\d\d:\d\d$/);
});

test('проверка регистрации и входа сохраняет правила и сообщения', () => {
  assert.deepEqual(credentialErrors({ login: '', password: '' }, false), { login: 'Минимум 3 символа', password: 'Введите пароль' });
  assert.deepEqual(credentialErrors({ login: 'user', password: 'short', full_name: ' ' }, true, true), { password: 'Минимум 12 символов', full_name: 'Укажите имя', email: 'Некорректный email' });
  assert.deepEqual(credentialErrors({ login: ' user ', password: '123456789012', full_name: 'Имя' }, true), {});
});

test('профиль нормализует имя и необязательный email', () => {
  assert.deepEqual(profileInput({ full_name: ' Имя ', email: '' }), { full_name: 'Имя', email: null });
  assert.deepEqual(profileInput({ full_name: 'Имя', email: 'a@example.test' }), { full_name: 'Имя', email: 'a@example.test' });
  assert.throws(() => profileInput({ full_name: ' ', email: '' }), /Укажите имя/);
});
