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

  // F34. Two verbs, not one /check-in carrying {"checked_in": bool}: the guards
  // differ (check-in requires status = 'confirmed', the undo requires nothing),
  // and one handler would collapse that into a body of ifs.
  it("posts the check-in and its undo to their own verb sub-paths, with no body", async () => {
    const paths: string[] = [];
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.checkInBooking(BOOKING_ID);
    await api.undoBookingCheckIn(BOOKING_ID);
    for (const call of fetchMock.mock.calls) {
      const [path, init] = call as [string, RequestInit];
      expect(init.method).toBe("POST");
      // The booking id is the whole request; neither route takes a body.
      expect(init.body).toBeUndefined();
      paths.push(path);
    }
    expect(paths).toEqual([
      `/manage/bookings/${BOOKING_ID}/check-in`,
      `/manage/bookings/${BOOKING_ID}/undo-check-in`,
    ]);
  });

  it("encodes the booking id on the check-in path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { id: BOOKING_ID }));
    await api.checkInBooking("b 1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/manage/bookings/b%201/check-in",
      expect.objectContaining({ method: "POST" }),
    );
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

describe("the floor client", () => {
  it("reads the floor from the envelope endpoint", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { staff: [] }));
    await api.getFloor();
    expect(fetchMock.mock.calls[0][0]).toBe("/manage/floor");
  });

  it("posts each break toggle to its own path and encodes the id", async () => {
    const started = stubFetch(() => jsonResponse(200, { id: "a b/c" }));
    await api.startStaffBreak("a b/c");
    expect(started.mock.calls[0][0]).toBe("/manage/floor/staff/a%20b%2Fc/break/start");
    expect(started.mock.calls[0][1]).toMatchObject({ method: "POST" });

    const ended = stubFetch(() => jsonResponse(200, { id: "a b/c" }));
    await api.endStaffBreak("a b/c");
    expect(ended.mock.calls[0][0]).toBe("/manage/floor/staff/a%20b%2Fc/break/end");
    expect(ended.mock.calls[0][1]).toMatchObject({ method: "POST" });
  });

  it("surfaces a toggle's 403 and 404 as ApiError codes the panel can map", async () => {
    // The panel treats them DIFFERENTLY — 403 is terminal for the whole panel
    // (deck P-6) and 404 is an in-card alert — so both must arrive as
    // distinguishable ApiErrors rather than as one generic failure.
    for (const [status, code] of [
      [403, "NOT_AUTHORIZED"],
      [404, "NOT_FOUND"],
    ] as const) {
      stubFetch(() => jsonResponse(status, { error: { code, message: "…" } }));
      await expect(api.startStaffBreak("id")).rejects.toMatchObject({ status, code });
    }
  });
});

// --- the fitting rooms (Feature 36) ---

const ROOM_ID = "aaaaaaaa-1111-2222-3333-444444444444";
const ASSIGNMENT_ID = "bbbbbbbb-1111-2222-3333-444444444444";
const BINDING_ID = "cccccccc-1111-2222-3333-444444444444";
const DRESS_ID = "dddddddd-1111-2222-3333-444444444444";
const STAFF_ID = "eeeeeeee-1111-2222-3333-444444444444";

describe("the fitting-room client", () => {
  it("hits all ten routes with their verb, their path and their body verbatim", async () => {
    // No case-conversion layer in this app: every body below is the backend's
    // own snake_case spelling, sent as written. Ten rows, one per route in
    // floor/router.py's F36 half.
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.createRoom({ label: "חדר 2", sort_order: 0 });
    await api.updateRoom(ROOM_ID, { label: "הבמה", sort_order: -1, is_active: false });
    await api.deleteRoom(ROOM_ID);
    await api.claimRoom(ROOM_ID, { booking_id: BOOKING_ID });
    await api.releaseAssignment(ASSIGNMENT_ID);
    await api.handoverAssignment(ASSIGNMENT_ID, { staff_user_id: STAFF_ID });
    await api.addAssignmentDress(ASSIGNMENT_ID, { dress_id: DRESS_ID, size_label: "38" });
    await api.removeAssignmentDress(ASSIGNMENT_ID, BINDING_ID);
    await api.listFloorDresses();
    await api.listFloorClients();

    const calls = fetchMock.mock.calls.map((call) => {
      const [path, init] = call as [string, RequestInit];
      return [
        init.method,
        path,
        init.body === undefined ? undefined : JSON.parse(init.body as string),
      ];
    });
    expect(calls).toEqual([
      ["POST", "/manage/floor/rooms", { label: "חדר 2", sort_order: 0 }],
      [
        "PATCH",
        `/manage/floor/rooms/${ROOM_ID}`,
        { label: "הבמה", sort_order: -1, is_active: false },
      ],
      ["DELETE", `/manage/floor/rooms/${ROOM_ID}`, undefined],
      ["POST", `/manage/floor/rooms/${ROOM_ID}/claim`, { booking_id: BOOKING_ID }],
      ["POST", `/manage/floor/assignments/${ASSIGNMENT_ID}/release`, undefined],
      [
        "POST",
        `/manage/floor/assignments/${ASSIGNMENT_ID}/handover`,
        { staff_user_id: STAFF_ID },
      ],
      [
        "POST",
        `/manage/floor/assignments/${ASSIGNMENT_ID}/dresses`,
        { dress_id: DRESS_ID, size_label: "38" },
      ],
      [
        "DELETE",
        `/manage/floor/assignments/${ASSIGNMENT_ID}/dresses/${BINDING_ID}`,
        undefined,
      ],
      ["GET", "/manage/floor/dresses", undefined],
      ["GET", "/manage/floor/clients", undefined],
    ]);
  });

  it("sends an EMPTY object for the anonymous claim, never no body at all", async () => {
    // The route's body model is required (`body: ClaimRoomRequest`, no default),
    // so the one-tap anonymous claim — the default path, and the only one
    // available before the day's first arrival — has to send `{}`.
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.claimRoom(ROOM_ID, {});
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe("{}");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
  });

  it("encodes every id it puts in a path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.removeAssignmentDress("a b/c", "d e/f");
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/manage/floor/assignments/a%20b%2Fc/dresses/d%20e%2Ff",
    );
  });

  it("carries a 409's details onto the ApiError so the tile can name the occupant", async () => {
    // D14. The `details` object is a real extension of an envelope every other
    // body treats as a two-field constant, and it exists on exactly these two
    // codes: the ruling requires the 409 to NAME the current occupant, and a
    // second GET would race the release it describes.
    stubFetch(() =>
      jsonResponse(409, {
        error: {
          code: "ROOM_OCCUPIED",
          message: "This fitting room is already claimed.",
          details: { staff_display_name: "דנה" },
        },
      }),
    );
    await expect(api.claimRoom(ROOM_ID, {})).rejects.toMatchObject({
      status: 409,
      code: "ROOM_OCCUPIED",
      details: { staff_display_name: "דנה" },
    });

    stubFetch(() =>
      jsonResponse(409, {
        error: {
          code: "STAFF_OCCUPIED",
          message: "That staff member is already in a fitting room.",
          details: { room_label: "חדר 5" },
        },
      }),
    );
    await expect(
      api.handoverAssignment(ASSIGNMENT_ID, { staff_user_id: STAFF_ID }),
    ).rejects.toMatchObject({ status: 409, code: "STAFF_OCCUPIED", details: { room_label: "חדר 5" } });
  });

  it("leaves details UNDEFINED, never null, on a 409 that names nobody", async () => {
    // ⚠ The occupant can release between the index violation and the occupant
    // read, so the server omits `details` entirely rather than shipping
    // {"staff_display_name": null}. `undefined` is what lets the panel select
    // rooms.error.roomOccupiedUnknown instead of interpolating an empty name
    // into a Hebrew sentence on a legally binding surface.
    stubFetch(() =>
      jsonResponse(409, {
        error: { code: "ROOM_OCCUPIED", message: "This fitting room is already claimed." },
      }),
    );
    const failure: unknown = await api.claimRoom(ROOM_ID, {}).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).details).toBeUndefined();
    expect((failure as ApiError).code).toBe("ROOM_OCCUPIED");
  });

  it("leaves details undefined on every error body that carries none", async () => {
    stubFetch(() => jsonResponse(404, { error: { code: "NOT_FOUND", message: "gone" } }));
    const failure: unknown = await api
      .releaseAssignment(ASSIGNMENT_ID)
      .catch((error: unknown) => error);
    expect((failure as ApiError).status).toBe(404);
    expect((failure as ApiError).details).toBeUndefined();
  });
});

// --- the queue verbs (Feature 58) ---

const TICKET_ID = "ffffffff-1111-2222-3333-444444444444";

describe("the dispatch client", () => {
  it("hits all five routes with their verb, their path and their body verbatim", async () => {
    // ⚠ EVERY PATH'S SECOND SEGMENT IS `floor`, which is why
    // apps/manage/vite.config.ts needs no edit — test_spa_serving.py asserts
    // set equality between the live route table's second segments and the
    // manage dev proxy's alternation, and a mismatch breaks ONLY a developer's
    // machine while production, CI and the whole suite stay green.
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.takeNext(ROOM_ID, {});
    await api.assignFromQueue(ROOM_ID, { queue_ticket_id: TICKET_ID });
    await api.callQueueTicket(TICKET_ID);
    await api.skipQueueTicket(TICKET_ID, { seen_skip_count: 0 });
    await api.removeQueueTicket(TICKET_ID);

    const calls = fetchMock.mock.calls.map((call) => {
      const [path, init] = call as [string, RequestInit];
      return [
        init.method,
        path,
        init.body === undefined ? undefined : JSON.parse(init.body as string),
      ];
    });
    expect(calls).toEqual([
      ["POST", `/manage/floor/rooms/${ROOM_ID}/take-next`, {}],
      [
        "POST",
        `/manage/floor/rooms/${ROOM_ID}/assign`,
        { queue_ticket_id: TICKET_ID },
      ],
      ["POST", `/manage/floor/queue/${TICKET_ID}/call`, undefined],
      ["POST", `/manage/floor/queue/${TICKET_ID}/skip`, { seen_skip_count: 0 }],
      ["POST", `/manage/floor/queue/${TICKET_ID}/remove`, undefined],
    ]);
  });

  it("sends seen_skip_count ZERO as a real field, never an omitted one", async () => {
    // ⚠ `SkipRequest.seen_skip_count` has NO server-side default: a caller that
    // omits it is a caller that did not read a count, and guessing 0 for her is
    // the exact failure the field exists to prevent. 0 is falsy in JS and this
    // is the row that catches a `...(count ? {count} : {})` "tidy-up".
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.skipQueueTicket(TICKET_ID, { seen_skip_count: 0 });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe('{"seen_skip_count":0}');
  });

  it("encodes the ticket id it puts in a path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { ok: true }));
    await api.callQueueTicket("a b/c");
    expect(fetchMock.mock.calls[0][0]).toBe("/manage/floor/queue/a%20b%2Fc/call");
  });

  it("carries a queue 409's details onto the ApiError so the row can pick its sentence", async () => {
    // One code, three sentences (design.md F-5): `details.status` chooses
    // between «היא כבר בטיפול.» and «הכניסה הזו נסגרה.», which are different
    // remedies — go and find her in a fitting room, versus nothing to do.
    stubFetch(() =>
      jsonResponse(409, {
        error: {
          code: "QUEUE_TICKET_NOT_WAITING",
          message: "That queue ticket is no longer waiting.",
          details: { status: "in_service" },
        },
      }),
    );
    await expect(api.callQueueTicket(TICKET_ID)).rejects.toMatchObject({
      status: 409,
      code: "QUEUE_TICKET_NOT_WAITING",
      details: { status: "in_service" },
    });
  });

  it("leaves a queue 409's details UNDEFINED, never null, when the body carries none", async () => {
    // `ApiError.details` is typed `Record<string, string> | undefined`, so the
    // {"status": null} shape cannot be constructed at all — which is what lets
    // the row select waitlist.error.ticketNotWaitingUnknown rather than
    // guessing at a remedy.
    stubFetch(() =>
      jsonResponse(409, {
        error: {
          code: "QUEUE_TICKET_NOT_WAITING",
          message: "That queue ticket is no longer waiting.",
        },
      }),
    );
    const failure: unknown = await api.callQueueTicket(TICKET_ID).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).details).toBeUndefined();
    expect((failure as ApiError).code).toBe("QUEUE_TICKET_NOT_WAITING");
  });

  it("surfaces the empty-queue 409 as its own code, not as a generic failure", async () => {
    // Spec D3 buys this code so a manager whose queue is simply empty is not
    // told a load failed, in the muted outage register, on top.
    stubFetch(() =>
      jsonResponse(409, { error: { code: "QUEUE_EMPTY", message: "The queue is empty." } }),
    );
    await expect(api.takeNext(ROOM_ID, {})).rejects.toMatchObject({
      status: 409,
      code: "QUEUE_EMPTY",
    });
  });
});

// --- customers CRM (Feature 53) ---

const CUSTOMER_ID = "33333333-4444-5555-6666-777777777777";

describe("customer endpoints", () => {
  it("sends paging plus the trimmed search term as query parameters", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await api.listCustomers({ q: "  מיכל  ", offset: 50, limit: 50 });
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    const query = new URL(path, "https://bella.example.test").searchParams;
    expect(path.startsWith("/manage/customers?")).toBe(true);
    expect(query.get("q")).toBe("מיכל");
    expect(query.get("offset")).toBe("50");
    expect(query.get("limit")).toBe("50");
  });

  // A blank box means "everyone", and the server drops a whitespace-only term
  // anyway — sending `q=` would put two spellings of one intent in the access
  // log for no gain.
  it("omits a whitespace-only term rather than sending a blank filter", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await api.listCustomers({ q: "   ", offset: 0, limit: 50 });
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).not.toContain("q=");
  });

  it("reads one customer by id and encodes it into the path", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.getCustomer("a b/c");
    expect(fetchMock.mock.calls[0][0]).toBe("/manage/customers/a%20b%2Fc");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "GET" });
  });

  // Real verbs and a path parameter are the shipped /manage convention — three
  // router docstrings say so. Partial by design: an omitted key means
  // "unchanged", and the server reads an all-unchanged patch as a no-op that
  // writes no audit row.
  it("patches only the fields it was given, under PATCH", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.updateCustomer(CUSTOMER_ID, { tags: ["VIP", "כלה"] });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe(`/manage/customers/${CUSTOMER_ID}`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ tags: ["VIP", "כלה"] });
  });

  it("can clear both mutable fields in one patch", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.updateCustomer(CUSTOMER_ID, { notes: "", tags: [] });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ notes: "", tags: [] });
  });

  it("surfaces a 404 as an ApiError code the detail can map", async () => {
    stubFetch(() => jsonResponse(404, { error: { code: "NOT_FOUND", message: "…" } }));
    await expect(api.getCustomer(CUSTOMER_ID)).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
    });
  });
});
