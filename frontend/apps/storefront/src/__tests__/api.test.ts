import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  FALLBACK_ERROR_MESSAGE,
  api,
  apiFetch,
  errorMessage,
  getBoutiqueOnce,
  isNotFound,
  resetBoutiqueCache,
} from "../api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// A Response body is single-use — hand out a fresh one per fetch call.
function stubFetch(makeResponse: () => Response) {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(makeResponse()));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  resetBoutiqueCache();
});

describe("apiFetch error extraction", () => {
  it("extracts the backend error code and message from the house shape", async () => {
    stubFetch(() =>
      jsonResponse(404, { error: { code: "NOT_FOUND", message: "Dress not found." } }),
    );
    await expect(apiFetch("/storefront/dresses/x")).rejects.toBeInstanceOf(ApiError);
    await expect(apiFetch("/storefront/dresses/x")).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
      message: "Dress not found.",
    });
  });

  it("falls back to the Hebrew default when the error body is not JSON", async () => {
    stubFetch(() => new Response("<html>bad gateway</html>", { status: 502 }));
    await expect(apiFetch("/storefront/boutique")).rejects.toMatchObject({
      status: 502,
      code: "UNKNOWN",
      message: FALLBACK_ERROR_MESSAGE,
    });
  });

  it("falls back when the JSON body lacks the error envelope", async () => {
    stubFetch(() => jsonResponse(500, { detail: "oops" }));
    await expect(apiFetch("/storefront/boutique")).rejects.toMatchObject({
      status: 500,
      code: "UNKNOWN",
      message: FALLBACK_ERROR_MESSAGE,
    });
  });

  it("surfaces a Hebrew message for a non-ApiError throw", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toBe(FALLBACK_ERROR_MESSAGE);
    expect(errorMessage(new ApiError(429, "TOO_MANY_ATTEMPTS", "רגע."))).toBe("רגע.");
  });

  it("recognises the archived/unknown-dress 404 the detail page renders", () => {
    expect(isNotFound(new ApiError(404, "NOT_FOUND", "x"))).toBe(true);
    expect(isNotFound(new ApiError(404, "TENANT_NOT_FOUND", "x"))).toBe(true);
    expect(isNotFound(new ApiError(500, "UNKNOWN", "x"))).toBe(false);
    expect(isNotFound(new Error("boom"))).toBe(false);
  });

  it("counts a malformed dress id as the same miss — a 400 the visitor cannot retry away", () => {
    // FastAPI's UUID coercion failure, normalised platform-wide to 400
    // VALIDATION_ERROR. Semantically "no such dress", not "the server broke".
    expect(isNotFound(new ApiError(400, "VALIDATION_ERROR", "bad id"))).toBe(true);
    // A 400 that is NOT a validation failure stays a failure with a retry.
    expect(isNotFound(new ApiError(400, "SOMETHING_ELSE", "x"))).toBe(false);
  });
});

describe("apiFetch request mechanics", () => {
  it("never sends credentials — this is a public surface and a cookie here is a cookie in a log", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { items: [] }));
    await api.listDresses(0);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("omit");
  });

  it("sends no body and no content-type — the storefront is three GETs", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.getBoutique();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers).toBeUndefined();
  });
});

describe("storefront endpoints", () => {
  it("sends offset as the only list parameter — limit is server-pinned at 24", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { items: [], total: 0, offset: 24, limit: 24 }),
    );
    await api.listDresses(24);
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    const query = new URL(path, "https://bella.example.test").searchParams;
    expect(query.get("offset")).toBe("24");
    expect(query.get("limit")).toBe(null);
  });

  it("encodes the dress id into the detail path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.getDress("d 1");
    expect(fetchMock.mock.calls[0][0]).toBe("/storefront/dresses/d%201");
  });

  it("reads the boutique block from its own endpoint", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.getBoutique();
    expect(fetchMock.mock.calls[0][0]).toBe("/storefront/boutique");
  });
});

describe("getBoutiqueOnce", () => {
  it("fetches once for the footer and the page body together", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { name: "בלה" }));
    const [a, b] = await Promise.all([getBoutiqueOnce(), getBoutiqueOnce()]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(a).toBe(b);
    await getBoutiqueOnce();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("drops the failed attempt so a retry actually retries", async () => {
    const fetchMock = stubFetch(() => jsonResponse(503, { error: { code: "X", message: "y" } }));
    await expect(getBoutiqueOnce()).rejects.toBeInstanceOf(ApiError);
    await expect(getBoutiqueOnce()).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
