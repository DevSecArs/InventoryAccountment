import { test, afterEach, mock } from 'node:test';
import { strict as assert } from 'node:assert';
import { apiRequest, apiBlobRequest, ApiError, setCsrfToken, setUnauthorizedHandler } from '../../src/api/client.js';

afterEach(() => { mock.restoreAll(); setCsrfToken(undefined); setUnauthorizedHandler(undefined); });

test('передаёт cookies, CSRF и идентификатор изменяющего запроса', async () => {
  setCsrfToken('csrf');
  const fetchMock = mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }));
  assert.equal(await apiRequest('/api/test', { method: 'POST', body: '{}' }), undefined);
  const [path, options] = fetchMock.mock.calls[0].arguments;
  assert.equal(path, '/api/test');
  assert.equal(options.credentials, 'include');
  assert.equal(options.headers.get('X-CSRF-Token'), 'csrf');
  assert.ok(options.headers.get('X-Request-ID'));
  assert.equal(options.headers.get('Content-Type'), 'application/json');
});

test('сохраняет ошибку сервера и request_id', async () => {
  mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ message: 'Ошибка', code: 'bad', request_id: 'server' }), { status: 400 }));
  await assert.rejects(apiRequest('/api/test'), error => error instanceof ApiError && error.code === 'bad' && error.requestId === 'server');
});

test('обрабатывает ответ не в JSON и скачивает CSV', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => new Response('ошибка', { status: 500 }));
  await assert.rejects(apiRequest('/api/test'), /неизвестном формате/);
  fetchMock.mock.mockImplementation(async () => new Response('a,b'));
  assert.equal(await (await apiBlobRequest('/api/export')).text(), 'a,b');
});

test('создаёт UUID при отсутствии randomUUID', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: { getRandomValues(bytes) { bytes.set(Array.from({ length: 16 }, (_, index) => index)); return bytes; } } });
  try {
    const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({ status: 'ok' }));
    assert.deepEqual(await apiRequest('/health/live'), { status: 'ok' });
    assert.equal(fetchMock.mock.calls[0].arguments[1].headers.get('X-Request-ID'), '00010203-0405-4607-8809-0a0b0c0d0e0f');
  } finally { Object.defineProperty(globalThis, 'crypto', original); }
});

test('ответ 401 уведомляет сеанс и сохраняет ошибку', async () => {
  let called = 0;
  setUnauthorizedHandler(() => { called += 1; });
  mock.method(globalThis, 'fetch', async () => Response.json({ message: 'Требуется вход' }, { status: 401 }));
  await assert.rejects(apiRequest('/api/private'), error => error instanceof ApiError && error.status === 401);
  assert.equal(called, 1);
});

test('запрос получает UUID даже без Web Crypto', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined });
  try {
    const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({}));
    await apiRequest('/health/live');
    assert.match(fetchMock.mock.calls[0].arguments[1].headers.get('X-Request-ID'), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  } finally { Object.defineProperty(globalThis, 'crypto', original); }
});

test('ошибка с JSON null сохраняет HTTP-статус', async () => {
  mock.method(globalThis, 'fetch', async () => new Response('null', { status: 500 }));
  await assert.rejects(apiRequest('/api/private'), error => error instanceof ApiError && error.status === 500);
});

test('переход отменяет запрос и не повторяет изменяющую операцию', async () => {
  const controller = new AbortController();
  const fetchMock = mock.method(globalThis, 'fetch', (_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => reject(new DOMException('Отменено', 'AbortError')), { once: true });
  }));
  const request = apiRequest('/api/test', { method: 'POST', body: '{}', signal: controller.signal });
  controller.abort();
  await assert.rejects(request, { name: 'AbortError' });
  assert.equal(fetchMock.mock.calls.length, 1);
});

test('запоздавший 401 отменённого запроса не завершает новый сеанс', async () => {
  const controller = new AbortController();
  let finish;
  let expired = 0;
  setUnauthorizedHandler(() => { expired += 1; });
  mock.method(globalThis, 'fetch', () => new Promise(resolve => { finish = resolve; }));
  const request = apiRequest('/api/private', { signal: controller.signal });
  controller.abort();
  finish(Response.json({ message: 'Истекла сессия' }, { status: 401 }));
  await assert.rejects(request, error => error instanceof ApiError && error.status === 401);
  assert.equal(expired, 0);
});

test('безопасные методы не отправляют CSRF, а серверный заголовок сохраняется при ошибке', async () => {
  setCsrfToken('csrf');
  const fetchMock = mock.method(globalThis, 'fetch', async () => new Response('ошибка', { status: 403, headers: { 'X-Request-ID': 'server-id' } }));
  await assert.rejects(apiRequest('/api/test', { method: 'GET' }), error => error instanceof ApiError && error.requestId === 'server-id');
  assert.equal(fetchMock.mock.calls[0].arguments[1].headers.has('X-CSRF-Token'), false);
});

test('ошибка CSV сохраняет request_id и позволяет явную повторную попытку', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => Response.json({ code: 'unavailable', message: 'Экспорт недоступен', request_id: 'export-id' }, { status: 503 }));
  await assert.rejects(apiBlobRequest('/api/export'), error => error instanceof ApiError && error.code === 'unavailable' && error.requestId === 'export-id');
  assert.equal(fetchMock.mock.calls.length, 1);
  fetchMock.mock.mockImplementation(async () => new Response('sku,quantity\nTEST,0.100'));
  assert.equal(await (await apiBlobRequest('/api/export')).text(), 'sku,quantity\nTEST,0.100');
  assert.equal(fetchMock.mock.calls.length, 2);
});
