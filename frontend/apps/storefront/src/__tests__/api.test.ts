import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  FALLBACK_ERROR_MESSAGE,
  api,
  apiFetch,
  errorMessage,
  errorMessageKey,
  errorMessageOr,
  getBoutiqueOnce,
  isNotFound,
  resetBoutiqueCache,
} from "../api";
import i18n from "../i18n";

// The real Hebrew catalogue, not a stub: the whole point of the mapping is that
// a real translation comes back, so a stubbed t() would pass on a missing key.
const t = (key: string): string => i18n.t(key);

const LATIN = /[A-Za-z]/;

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

  it("turns a 200 that answers HTML into an ApiError, not a SyntaxError", async () => {
    // Not hypothetical: under the SPA history fallback, with no backend behind
    // the dev proxy, /storefront/dresses answers 200 text/html — exactly the
    // state the blocking e2e job runs in. A raw SyntaxError escapes the page's
    // catch and blanks the screen instead of rendering the error card.
    stubFetch(
      () =>
        new Response("<!doctype html><title>storefront</title>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        }),
    );
    const error: unknown = await apiFetch("/storefront/dresses").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).not.toBeInstanceOf(SyntaxError);
    expect(error).toMatchObject({ status: 200, code: "UNKNOWN", message: FALLBACK_ERROR_MESSAGE });
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

  it("sends no body and no content-type on GETs", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, {}));
    await api.getBoutique();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers).toBeUndefined();
  });

  it("posts JSON with credentials still omitted — the token travels in the body, never a cookie", async () => {
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }));
    await api.sendOtp("0501234567");
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/storefront/otp/send");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("omit");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({ phone: "0501234567" });
  });

  it("resolves a 204 without trying to parse a body", async () => {
    stubFetch(() => new Response(null, { status: 204 }));
    await expect(api.sendOtp("0501234567")).resolves.toBeUndefined();
  });
});

// Every backend message is English. Rendering ApiError.message would paint
// English onto a Hebrew-only page for a suspended tenant, an unknown slug, an
// archived dress or a throttle trip — so the CODE selects the key and the
// message is never shown. The Latin-letter assertion is the actual guard: it
// fails the moment anyone "helpfully" falls back to error.message.
describe("errorMessage", () => {
  it.each([
    ["TENANT_NOT_FOUND", "No active boutique at this address.", "errors.tenantNotFound"],
    ["NOT_FOUND", "Resource not found.", "errors.notFound"],
    ["TOO_MANY_ATTEMPTS", "Too many attempts. Try again later.", "errors.tooManyAttempts"],
    ["VALIDATION_ERROR", "Input failed validation.", "errors.validation"],
    ["SLOT_UNAVAILABLE", "Slot is no longer available.", "errors.slotUnavailable"],
    ["TERMS_STALE", "Terms version is stale.", "errors.termsStale"],
    ["OTP_INVALID", "Invalid code.", "errors.otpInvalid"],
    ["OTP_EXPIRED", "Code expired.", "errors.otpExpired"],
    ["PHONE_NOT_VERIFIED", "Phone not verified.", "errors.phoneNotVerified"],
    ["SMS_NOT_CONFIGURED", "SMS is not configured.", "errors.smsUnavailable"],
    ["SMS_UNAVAILABLE", "SMS provider unavailable.", "errors.smsUnavailable"],
  ])("renders Hebrew for %s and never the server's English", (code, english, key) => {
    const rendered = errorMessage(new ApiError(400, code, english), t);

    expect(errorMessageKey(new ApiError(400, code, english))).toBe(key);
    expect(rendered).toBe(t(key));
    expect(rendered).not.toBe(english);
    expect(rendered).not.toMatch(LATIN);
    // A missing resource makes i18next echo the key back, which is Latin — so
    // the assertion above also catches a key that was renamed out from under us.
    expect(rendered).not.toBe(key);
  });

  it("falls back to real Hebrew for an unmapped code and for a non-ApiError", () => {
    expect(errorMessage(new ApiError(500, "KAFKA_EXPLODED", "boom"), t)).toBe(t("errors.unknown"));
    expect(errorMessage(new TypeError("Failed to fetch"), t)).toBe(t("errors.unknown"));
    expect(t("errors.unknown")).not.toMatch(LATIN);
  });
});

describe("errorMessageOr", () => {
  it("uses the surface's own copy when the code carries nothing useful", () => {
    // A dropped connection on the catalog should say "we could not load the
    // collection", not a generic apology.
    expect(errorMessageOr(new TypeError("Failed to fetch"), t, "catalog.error")).toBe(
      t("catalog.error"),
    );
    expect(errorMessageOr(new ApiError(500, "KAFKA_EXPLODED", "boom"), t, "dress.error")).toBe(
      t("dress.error"),
    );
  });

  it("keeps the mapped message when the code does say something", () => {
    // A throttle trip must still say so — the surface fallback does not win.
    expect(
      errorMessageOr(new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts."), t, "catalog.error"),
    ).toBe(t("errors.tooManyAttempts"));
    expect(errorMessageOr(new ApiError(429, "TOO_MANY_ATTEMPTS", "x"), t, "catalog.error")).not.toBe(
      t("catalog.error"),
    );
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

  it("reads the current terms from /storefront/terms", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, {
        version: 3,
        terms_text: "טקסט",
        refundable_until_hours_before: 48,
        forfeit_percent: 100,
      }),
    );
    const terms = await api.getTerms();
    expect(fetchMock.mock.calls[0][0]).toBe("/storefront/terms");
    expect(terms.version).toBe(3);
    expect(terms.refundable_until_hours_before).toBe(48);
  });

  it("reads the appointment types from /storefront/appointment-types", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, []));
    await api.listAppointmentTypes();
    expect(fetchMock.mock.calls[0][0]).toBe("/storefront/appointment-types");
  });

  it("sends the slot window as from/to query dates", async () => {
    const fetchMock = stubFetch(() => jsonResponse(200, { slots: [] }));
    await api.listSlots("2026-08-01", "2026-08-14");
    const [path] = fetchMock.mock.calls[0] as [string, RequestInit];
    const query = new URL(path, "https://bella.example.test").searchParams;
    expect(query.get("from")).toBe("2026-08-01");
    expect(query.get("to")).toBe("2026-08-14");
  });

  it("verifies the code with phone and code and hands back the bearer token", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { verification_token: "tok", expires_at: "2026-08-01T10:00:00Z" }),
    );
    const result = await api.verifyOtp("0501234567", "123456");
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/storefront/otp/verify");
    expect(JSON.parse(init.body as string)).toEqual({ phone: "0501234567", code: "123456" });
    expect(result.verification_token).toBe("tok");
  });

  it("posts the booking with the backend's exact snake_case field names", async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(201, {
        id: "b-1",
        starts_at: "2026-08-04T13:30:00+03:00",
        status: "confirmed",
        appointment_type_name: "מדידה",
        dress_name: null,
        dress_size: null,
      }),
    );
    const created = await api.createBooking({
      phone: "0501234567",
      verification_token: "tok",
      name: "דנה",
      appointment_type_id: "a-1",
      starts_at: "2026-08-04T13:30:00.000Z",
      terms_version: 3,
      dress_id: null,
      dress_size: null,
      notes: null,
    });
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/storefront/bookings");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      phone: "0501234567",
      verification_token: "tok",
      name: "דנה",
      appointment_type_id: "a-1",
      starts_at: "2026-08-04T13:30:00.000Z",
      terms_version: 3,
      dress_id: null,
      dress_size: null,
      notes: null,
    });
    expect(created.appointment_type_name).toBe("מדידה");
  });
});

// isNotFound folds 400 VALIDATION_ERROR into "dress gone" — correct on the
// dress detail, where a malformed id is the only 400, and WRONG on the booking
// POST, where a schema 400 is a form problem, not a vanished dress. This pins
// that the mapping the booking flow actually uses disagrees with isNotFound on
// exactly that error, so routing booking failures through isNotFound would
// fail here, not in production.
describe("booking-path VALIDATION_ERROR stays out of isNotFound", () => {
  it("maps a booking 400 VALIDATION_ERROR to the validation copy, never the dress-gone rendering", async () => {
    stubFetch(() =>
      jsonResponse(400, { error: { code: "VALIDATION_ERROR", message: "Input failed validation." } }),
    );
    const error: unknown = await api
      .createBooking({
        phone: "0501234567",
        verification_token: "tok",
        name: "דנה",
        appointment_type_id: "a-1",
        starts_at: "2026-08-04T13:30:00.000Z",
        terms_version: 3,
        dress_id: null,
        dress_size: null,
        notes: null,
      })
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    // The hazard is real: isNotFound WOULD misread this booking failure as a
    // vanished dress. errorMessageKey — the booking flow's only renderer —
    // does not.
    expect(isNotFound(error)).toBe(true);
    expect(errorMessageKey(error)).toBe("errors.validation");
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
