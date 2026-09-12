import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
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
