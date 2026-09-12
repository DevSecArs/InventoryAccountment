export interface ApiErrorBody {
  code?: string;
  message?: string;
  details?: unknown;
  request_id?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId?: string;

  constructor(status: number, body: ApiErrorBody, fallbackRequestId?: string) {
    super(body.message ?? `Запрос завершился с кодом ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code ?? `http_${status}`;
    this.details = body.details;
    this.requestId = body.request_id ?? fallbackRequestId;
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const requestId = crypto.randomUUID();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", requestId);

  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
    signal: init.signal,
  });

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = { message: "Сервер вернул ответ в неизвестном формате" };
    }
    throw new ApiError(response.status, body, responseRequestId);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
