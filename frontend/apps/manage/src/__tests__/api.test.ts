import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, apiFetch, FALLBACK_ERROR_MESSAGE } from "../api";

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
});

describe("apiFetch error extraction", () => {
  it("extracts the backend error code and message from the house shape", async () => {
    stubFetch(() =>
      jsonResponse(400, {
        error: { code: "VALIDATION_ERROR", message: "close_time must be after open_time" },
      }),
    );
    const failure = apiFetch("/manage/settings");
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(apiFetch("/manage/settings")).rejects.toMatchObject({
      status: 400,
      code: "VALIDATION_ERROR",
      message: "close_time must be after open_time",
    });
  });

  it("falls back to a generic message when the error body is not JSON", async () => {
    stubFetch(() => new Response("<html>bad gateway</html>", { status: 502 }));
    await expect(apiFetch("/manage/settings")).rejects.toMatchObject({
      status: 502,
      code: "UNKNOWN",
      message: FALLBACK_ERROR_MESSAGE,
    });
  });

  it("falls back when the JSON body lacks the error envelope", async () => {
    stubFetch(() => jsonResponse(500, { detail: "oops" }));
    await expect(apiFetch("/manage/settings")).rejects.toMatchObject({
      status: 500,
      code: "UNKNOWN",
      message: FALLBACK_ERROR_MESSAGE,
    });
  });
});

describe("apiFetch request mechanics", () => {
  it("always sends credentials: include", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.logout();
    expect(fetchMock).toHaveBeenCalledWith(
      "/manage/auth/logout",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("serializes JSON bodies with the content-type header", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { profile: {}, toggles: {} }));
    await api.updateSettings({ profile: { phone: "03-1234567" } });
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/manage/settings");
    expect(init.method).toBe("PUT");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({ profile: { phone: "03-1234567" } });
  });

  it("returns the parsed body on success", async () => {
    stubFetch(() =>
      jsonResponse(200, { profile: { phone: "03-1234567" }, toggles: { deposits_enabled: true } }),
    );
    const settings = await api.getSettings();
    expect(settings).toEqual({
      profile: { phone: "03-1234567" },
      toggles: { deposits_enabled: true },
    });
  });

  it("URL-encodes resource ids in paths", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.archiveAppointmentType("11111111-2222-3333-4444-555555555555");
    expect(fetchMock).toHaveBeenCalledWith(
      "/manage/appointment-types/11111111-2222-3333-4444-555555555555",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
