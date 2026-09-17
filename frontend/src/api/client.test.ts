import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, setCsrfToken } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(undefined);
});

describe("apiRequest", () => {
  it("передаёт cookie и CSRF-токен для изменяющего запроса", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("csrf-example");

    await apiRequest("/api/v1/auth/me", { method: "PUT", body: JSON.stringify({ full_name: "Тест" }) });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf-example");
  });

  it("передаёт идентификатор запроса и читает JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ status: string }>("/health/live")).resolves.toEqual({ status: "ok" });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("X-Request-ID")).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("создаёт идентификатор запроса без crypto.randomUUID", async () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.set(Array.from({ length: 16 }, (_, index) => index));
      return bytes;
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("crypto", { getRandomValues });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ status: string }>("/health/live")).resolves.toEqual({ status: "ok" });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("X-Request-ID")).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
    expect(getRandomValues).toHaveBeenCalledOnce();
  });

  it("сохраняет сообщение и request_id серверной ошибки", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ code: "conflict", message: "Код уже используется", request_id: "b934f332-4899-4aeb-8751-8f688771fd52" }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const error = await apiRequest("/api/v1/units/").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      message: "Код уже используется",
      requestId: "b934f332-4899-4aeb-8751-8f688771fd52",
    });
  });
});
