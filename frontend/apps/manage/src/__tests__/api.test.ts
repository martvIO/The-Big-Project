import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, apiFetch, FALLBACK_ERROR_MESSAGE, uploadToStorage } from "../api";
import type { PresignResponse } from "../api";

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

// --- catalog (Feature 8) ---

const presign: PresignResponse = {
  media_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  url: "https://media.example.test/boutique-media",
  fields: {
    key: "tenants/t1/dresses/d1/media/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg",
    "Content-Type": "image/jpeg",
    policy: "eyJ4IjoxfQ==",
    "x-amz-algorithm": "AWS4-HMAC-SHA256",
    "x-amz-credential": "AKIA/20260724/il-central-1/s3/aws4_request",
    "x-amz-date": "20260724T000000Z",
    "x-amz-signature": "deadbeef",
  },
  expires_in: 300,
  max_bytes: 10_485_760,
};

function photo(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0x00])], "IMG_4821.jpg", {
    type: "image/jpeg",
  });
}

describe("uploadToStorage", () => {
  it("posts to S3 without cookies and without a headers object", async () => {
    // No headers at all: the browser must set the multipart boundary itself,
    // and Content-Type travels as a form FIELD, not a header.
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }));
    await uploadToStorage(presign, photo());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(presign.url);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("omit");
    expect(init.headers).toBeUndefined();
  });

  it("appends every presign field in iteration order and `file` last", async () => {
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }));
    await uploadToStorage(presign, photo());
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const form = init.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect([...form.keys()]).toEqual([...Object.keys(presign.fields), "file"]);
    expect(form.get("Content-Type")).toBe("image/jpeg");
    expect(form.get("file")).toBeInstanceOf(File);
  });

  it("resolves on a 204 with an empty body without parsing it", async () => {
    const response = new Response(null, { status: 204 });
    const json = vi.spyOn(response, "json");
    const text = vi.spyOn(response, "text");
    stubFetch(() => response);
    await expect(uploadToStorage(presign, photo())).resolves.toBeUndefined();
    expect(json).not.toHaveBeenCalled();
    expect(text).not.toHaveBeenCalled();
  });

  it("rejects a 403 XML body as UPLOAD_FAILED without parsing the body", async () => {
    const response = new Response("<Error><Code>AccessDenied</Code></Error>", { status: 403 });
    const json = vi.spyOn(response, "json");
    const text = vi.spyOn(response, "text");
    stubFetch(() => response);
    await expect(uploadToStorage(presign, photo())).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "UPLOAD_FAILED",
      message: "העלאת הקובץ נכשלה. נסי שוב.",
    });
    expect(json).not.toHaveBeenCalled();
    expect(text).not.toHaveBeenCalled();
  });

  it("maps a rejected fetch (network down / CORS preflight) to UPLOAD_BLOCKED", async () => {
    // fetch REJECTS with a bare TypeError here — it does not return a non-ok Response.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(uploadToStorage(presign, photo())).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      code: "UPLOAD_BLOCKED",
      message: "לא ניתן היה להעלות את הקובץ. בדקי את החיבור ונסי שוב.",
    });
  });
});

describe("catalog endpoints", () => {
  it("sends paging, search and the archived flag as query parameters", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { items: [], total: 0, offset: 0, limit: 24 }),
    );
    await api.listDresses({ offset: 24, limit: 24, search: "עלמה", archived: true });
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    const query = new URL(path, "https://bella.example.test").searchParams;
    expect(query.get("offset")).toBe("24");
    expect(query.get("limit")).toBe("24");
    expect(query.get("search")).toBe("עלמה");
    expect(query.get("archived")).toBe("true");
  });

  it("omits an empty search rather than sending a blank filter", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { items: [], total: 0, offset: 0, limit: 24 }),
    );
    await api.listDresses({ offset: 0, limit: 24, search: "", archived: false });
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).not.toContain("search=");
  });

  it("routes every media call under its dress and encodes the ids", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.confirmMedia("d 1", "m 1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/manage/dresses/d%201/media/m%201/confirm",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("replaces the whole variant matrix in one PUT", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.replaceVariants("d1", [{ size_label: "38", quantity: 3, sort_order: 0 }]);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/manage/dresses/d1/variants");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      variants: [{ size_label: "38", quantity: 3, sort_order: 0 }],
    });
  });

  it("reorders media as a full permutation under the order path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.reorderMedia("d1", ["m2", "m1"]);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/manage/dresses/d1/media/order");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ media_ids: ["m2", "m1"] });
  });
});

// --- owner bookings (Feature 15) ---

const BOOKING_ID = "77777777-8888-9999-aaaa-bbbbbbbbbbbb";

describe("owner booking endpoints", () => {
  it("sends the required date plus paging as query parameters", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await api.listBookings({ date: "2026-08-04", offset: 50, limit: 50 });
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    const query = new URL(path, "https://bella.example.test").searchParams;
    expect(query.get("date")).toBe("2026-08-04");
    expect(query.get("offset")).toBe("50");
    expect(query.get("limit")).toBe("50");
  });

  it("reads one booking under its encoded id", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.getBooking("b 1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/manage/bookings/b%201",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts each transition to its own verb sub-path", async () => {
    const paths: string[] = [];
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.confirmBooking(BOOKING_ID);
    await api.cancelBooking(BOOKING_ID);
    await api.noShowBooking(BOOKING_ID);
    await api.completeBooking(BOOKING_ID);
    for (const call of fetchMock.mock.calls) {
      const [path, init] = call as [string, RequestInit];
      expect(init.method).toBe("POST");
      expect(init.body).toBeUndefined();
      paths.push(path);
    }
    expect(paths).toEqual([
      `/manage/bookings/${BOOKING_ID}/confirm`,
      `/manage/bookings/${BOOKING_ID}/cancel`,
      `/manage/bookings/${BOOKING_ID}/no-show`,
      `/manage/bookings/${BOOKING_ID}/complete`,
    ]);
  });

  it("sends the reschedule target as an aware ISO instant", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.rescheduleBooking(BOOKING_ID, "2026-08-05T11:00:00Z");
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(`/manage/bookings/${BOOKING_ID}/reschedule`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ starts_at: "2026-08-05T11:00:00Z" });
  });

  it("sends the corrected phone exactly as typed — the server normalizes", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.correctBookingPhone(BOOKING_ID, "050-123 4567");
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(`/manage/bookings/${BOOKING_ID}/phone`);
    expect(JSON.parse(init.body as string)).toEqual({ phone: "050-123 4567" });
  });

  it("rotates the manage link through resend-link", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.resendBookingLink(BOOKING_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      `/manage/bookings/${BOOKING_ID}/resend-link`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("asks for the owner slot grid with the from/to aliases the router binds", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { slots: [] }));
    await api.listManageSlots("2026-08-04", "2026-08-17");
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    const query = new URL(path, "https://bella.example.test").searchParams;
    expect(path.startsWith("/manage/slots?")).toBe(true);
    expect(query.get("from")).toBe("2026-08-04");
    expect(query.get("to")).toBe("2026-08-17");
  });
});

// --- F51 staff endpoints ---

describe("staff endpoints", () => {
  it("lists staff with a bare GET", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, []));
    await api.listStaff();
    expect(fetchMock.mock.calls[0][0]).toBe("/manage/staff");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "GET" });
  });

  it("creates a staff member with the snake_case wire body verbatim", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.createStaff({
      email: "dana@bella.example",
      display_name: "דנה",
      role: "shift_manager",
      password: "a-long-enough-pw",
    });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/manage/staff");
    expect(init.method).toBe("POST");
    // No case-conversion layer in this app: the body is the backend's snake_case
    // spelling, sent as written.
    expect(JSON.parse(init.body)).toEqual({
      email: "dana@bella.example",
      display_name: "דנה",
      role: "shift_manager",
      password: "a-long-enough-pw",
    });
  });

  it("patches a staff member by id with only the fields it was given", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.updateStaff("11111111-2222-3333-4444-555555555555", { display_name: "דנה כהן" });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/manage/staff/11111111-2222-3333-4444-555555555555");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ display_name: "דנה כהן" });
  });

  it("encodes the id in the path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.deactivateStaff("a b/c");
    expect(fetchMock.mock.calls[0][0]).toBe("/manage/staff/a%20b%2Fc");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "DELETE" });
  });

  it("surfaces the three staff 409s as ApiError codes the section can map", async () => {
    for (const code of ["DUPLICATE_EMAIL", "LAST_OWNER_REQUIRED", "STAFF_SELF_MANAGE"]) {
      stubFetch(() => jsonResponse(409, { error: { code, message: "…" } }));
      await expect(
        api.createStaff({
          email: "dana@bella.example",
          display_name: "דנה",
          role: "owner",
          password: "a-long-enough-pw",
        }),
      ).rejects.toMatchObject({ status: 409, code });
    }
  });
});
