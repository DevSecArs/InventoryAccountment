export class ApiError extends Error {
  constructor(status, body, fallbackRequestId) {
    super(body.message ?? `Запрос завершился с кодом ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code ?? `http_${status}`;
    this.details = body.details;
    this.requestId = body.request_id ?? fallbackRequestId;
  }
}

let csrfToken;
let unauthorizedHandler;
export function setUnauthorizedHandler(handler) { unauthorizedHandler = handler; }
export function setCsrfToken(token) { csrfToken = token; }

function createRequestId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (typeof globalThis.crypto?.getRandomValues === 'function') globalThis.crypto.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const value = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
}

async function request(path, init, blob) {
  const requestId = createRequestId();
  const headers = new Headers(init.headers);
  if (!blob) headers.set('Accept', 'application/json');
  headers.set('X-Request-ID', requestId);
  if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes((init.method ?? 'GET').toUpperCase())) {
    headers.set('X-CSRF-Token', csrfToken);
  }
  if (!blob && init.body !== undefined) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...init, headers, credentials: 'include' });
  if (!response.ok) {
    let body;
    try { body = await response.json(); }
    catch { body = { message: 'Сервер вернул ответ в неизвестном формате' }; }
    if (!body || typeof body !== 'object' || Array.isArray(body)) body = {};
    if (response.status === 401 && !init.signal?.aborted && unauthorizedHandler) unauthorizedHandler();
    throw new ApiError(response.status, body, response.headers.get('X-Request-ID') ?? requestId);
  }
  if (blob) return response.blob();
  if (response.status === 204) return undefined;
  return response.json();
}

export function apiRequest(path, init = {}) { return request(path, init, false); }
export function apiBlobRequest(path, init = {}) { return request(path, init, true); }

