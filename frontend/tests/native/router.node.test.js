import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { shouldNavigate, startRouter } from '../../src/native/router.js';
const origin = 'http://localhost:8080';
const anchor = (href, target = '', download = false) => ({ href, target, hasAttribute: name => name === 'download' && download });
const event = overrides => ({ button: 0, ...overrides });
test('маршрутизатор оставляет внешние ссылки и специальные клики браузеру', () => {
  assert.equal(shouldNavigate(event({}), anchor(`${origin}/units?search=x`), origin), true);
  assert.equal(shouldNavigate(event({ ctrlKey: true }), anchor(`${origin}/units`), origin), false);
  assert.equal(shouldNavigate(event({}), anchor('https://example.com/'), origin), false);
  assert.equal(shouldNavigate(event({}), anchor(`${origin}/x`, '_blank'), origin), false);
  assert.equal(shouldNavigate(event({}), anchor(`${origin}/x`, '', true), origin), false);
});

test('навигация обновляет History API, а popstate повторно отображает маршрут', () => {
  const saved = Object.fromEntries(['document', 'window', 'history'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  const listeners = {};
  const calls = [];
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { addEventListener(name, handler) { listeners[name] = handler; } } });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { addEventListener(name, handler) { listeners[name] = handler; } } });
  Object.defineProperty(globalThis, 'history', { configurable: true, value: { pushState(...args) { calls.push(['push', ...args]); }, replaceState(...args) { calls.push(['replace', ...args]); } } });
  try {
    let renders = 0;
    const navigate = startRouter(() => { renders += 1; });
    navigate('/units?search=a'); navigate('/404', true); listeners.popstate();
    assert.deepEqual(calls, [['push', null, '', '/units?search=a'], ['replace', null, '', '/404']]);
    assert.equal(renders, 3);
  } finally {
    for (const [key, descriptor] of Object.entries(saved)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key];
    }
  }
});
