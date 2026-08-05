import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { themeTokens } from "@boutique/ui";
import type {
  AppointmentTypeRow,
  BookingCreateResponse,
  BoutiqueResponse,
  StorefrontDetail,
  StorefrontTerms,
} from "../api";
import { SlotPicker } from "@boutique/ui";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { SizeChips } from "../components/booking/SizeChips";
import { TypePicker } from "../components/booking/TypePicker";
import { BookPage } from "../routes/BookPage";
import { handOff, matchRoute, usePathname } from "../router";
import { expectFocus } from "../test/focus";
import { inPaintGap } from "../test/interleave";
import { PRIVACY_FIXTURE } from "../test/boutique";

// Spread the real module so ApiError and errorMessage* keep their real
// implementations — the load-failure copy under test is chosen by CODE mapping,
// and a stubbed mapper would assert nothing about it.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTerms: vi.fn(),
      listAppointmentTypes: vi.fn(),
      listSlots: vi.fn(),
      getDress: vi.fn(),
      sendOtp: vi.fn(),
      verifyOtp: vi.fn(),
      createBooking: vi.fn(),
      paymentStatus: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const paymentStatus = vi.mocked(api.paymentStatus);

// The document hand-off, stubbed for the whole file: jsdom refuses a real
// navigation, and a test that let one through would be asserting against a
// page the runner had already abandoned.
//
// A property spy rather than vi.mock("../router"), deliberately. router.tsx and
// BookPage.tsx are an import CYCLE, so the factory's own importActual resolves
// BookPage's `handOff` binding to the REAL module — the render assertions still
// pass and the redirect assertion silently sees zero calls. clearAllMocks()
// below clears the calls and keeps the implementation, which is what makes one
// module-scope spy enough.
const handOffSpy = vi.spyOn(handOff, "leave").mockImplementation(() => undefined);
const getTerms = vi.mocked(api.getTerms);
const listTypes = vi.mocked(api.listAppointmentTypes);
const listSlots = vi.mocked(api.listSlots);
const getDress = vi.mocked(api.getDress);
const sendOtp = vi.mocked(api.sendOtp);
const verifyOtp = vi.mocked(api.verifyOtp);
const createBooking = vi.mocked(api.createBooking);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const TERMS: StorefrontTerms = {
  version: 3,
  terms_text: "ביטול עד 48 שעות לפני המועד.",
  refundable_until_hours_before: 48,
  forfeit_percent: 50,
};

const DOWN = new ApiError(503, "UNKNOWN", "backend down");
const THROTTLED = new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts. Try again later.");
const GONE = new ApiError(404, "NOT_FOUND", "Resource not found.");
const OTP_WRONG = new ApiError(400, "OTP_INVALID", "Invalid code.");
const OTP_STALE = new ApiError(400, "OTP_EXPIRED", "Code expired.");
const TOKEN_DEAD = new ApiError(403, "PHONE_NOT_VERIFIED", "Phone not verified.");
const SLOT_TAKEN = new ApiError(409, "SLOT_UNAVAILABLE", "That time is no longer available.");
const TERMS_MOVED = new ApiError(409, "TERMS_STALE", "Terms have been republished.");
const BROKEN = new ApiError(500, "UNKNOWN", "boom");

function boutique(overrides: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: "052-1234567",
    address: "דיזנגוף 100, תל אביב",
    maps_url: null,
    instagram: "alma.bridal",
    hours: [],
    exceptions: [],
    ...PRIVACY_FIXTURE,
    ...overrides,
  };
}

function dressDetail(overrides: Partial<StorefrontDetail> = {}): StorefrontDetail {
  return {
    id: "d1",
    name: "שמלת אלמה",
    description: null,
    price_agorot: null,
    reserved: false,
    sizes: [
      { size_label: "36", available: true },
      { size_label: "38", available: false },
    ],
    media: [],
    ...overrides,
  };
}

function appointmentType(overrides: Partial<AppointmentTypeRow> = {}): AppointmentTypeRow {
  return {
    id: "t1",
    name: "מדידה ראשונה",
    duration_minutes: 45,
    audience: "all",
    deposit_required: false,
    deposit_amount_agorot: null,
    ...overrides,
  };
}

// Jerusalem runs UTC+3 in August; the suite's own clock is America/New_York.
// 07:00Z is 10:00 on the 4th in Jerusalem and 03:00 on the 4th in New York;
// 21:00Z is 00:00 on the FIFTH in Jerusalem and still 17:00 on the fourth in
// New York — the instant that tells the boutique's calendar from the device's.
const AUG4_1000 = "2026-08-04T07:00:00Z";
const AUG4_1045 = "2026-08-04T07:45:00Z";
const AUG4_1130 = "2026-08-04T08:30:00Z";
const AUG5_1000 = "2026-08-05T07:00:00Z";
const AUG5_0000 = "2026-08-04T21:00:00Z";

const SLOTS = [AUG4_1000, AUG4_1045, AUG5_1000];

// The number she types, and the one shape all three phone-carrying calls must
// agree on. A client that normalised differently across /otp/send, /otp/verify
// and /bookings answers PHONE_NOT_VERIFIED for a correct code.
const TYPED_PHONE = "050-123 4567";
const WIRE_PHONE = "+972501234567";

function booking(overrides: Partial<BookingCreateResponse> = {}): BookingCreateResponse {
  return {
    id: "b1",
    starts_at: AUG4_1000,
    status: "confirmed",
    appointment_type_name: "מדידה ראשונה",
    dress_name: null,
    dress_size: null,
    // F19's ordinary shape: no deposit due, so the flow still ends at the
    // confirmation screen and every test above is unchanged by this feature.
    deposit_due: false,
    redirect_url: null,
    payment_session_id: null,
    ...overrides,
  };
}

// The provider's hosted page and the poll credential. The session id is already
// client-visible by construction — it is embedded in the checkout URL the
// browser is about to visit — which is what lets it key the poll (D13).
const CHECKOUT = "https://pay.example.test/checkout/abc";
const SESSION = "ps_abc123";

function depositBooking(overrides: Partial<BookingCreateResponse> = {}): BookingCreateResponse {
  return booking({
    // `status` is pending_payment EXACTLY when deposit_due — a seat held with
    // the money not yet in.
    status: "pending_payment",
    deposit_due: true,
    redirect_url: CHECKOUT,
    payment_session_id: SESSION,
    ...overrides,
  });
}

function payFacts(
  overrides: Partial<Awaited<ReturnType<typeof api.paymentStatus>>> = {},
): Awaited<ReturnType<typeof api.paymentStatus>> {
  return {
    booking_status: "pending_payment",
    payment_status: "pending",
    paid_at: null,
    declined: false,
    ...overrides,
  };
}

function pending<T>(): Promise<T> {
  return new Promise<T>(() => {
    // never settles — holds the step in its loading state
  });
}

function deferred<T>(): { promise: Promise<T>; settle: (value: T) => void } {
  let settle!: (value: T) => void;
  const promise = new Promise<T>((resolve) => {
    settle = resolve;
  });
  return { promise, settle };
}

function renderBook(step: Parameters<typeof BookPage>[0]["step"] = "slot", dressId?: string) {
  // The step reads the boutique from the layout's single fetch, so the layout
  // is part of the unit under test — a bare <BookPage/> renders against a
  // context default that never resolves.
  return render(
    <StorefrontLayout>
      <BookPage step={step} dressId={dressId} />
    </StorefrontLayout>,
  );
}

// The steps are walked, never rendered cold: BookPage holds the whole flow in
// memory, so a later step is only honest when the earlier ones put it there.
// This is what the Router does — the same element in the same position — which
// is why the picked slot, the typed name and the accepted version survive.
function BookFlow() {
  const match = matchRoute(usePathname());
  return match.name === "book" ? <BookPage step={match.step} dressId={match.dressId} /> : null;
}

function renderFlow(path = "/book/slot") {
  window.history.replaceState(null, "", path);
  return render(
    <StorefrontLayout>
      <BookFlow />
    </StorefrontLayout>,
  );
}

async function pickFirstType() {
  fireEvent.click(await screen.findByRole("radio", { name: /מדידה ראשונה/ }));
}

function forward() {
  return screen.getByRole("button", { name: i18n.t("booking.continue") });
}

async function walkToDetails(dressId?: string) {
  const result = renderFlow(
    dressId === undefined ? "/book/slot" : `/book/slot/${encodeURIComponent(dressId)}`,
  );
  await pickFirstType();
  fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
  fireEvent.click(forward());
  return result;
}

async function walkToTerms(dressId?: string) {
  const result = await walkToDetails(dressId);
  fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
  fireEvent.change(screen.getByLabelText(i18n.t("booking.notes")), {
    target: { value: "מגיעה עם אמא" },
  });
  if (dressId !== undefined) {
    const size = screen.queryByRole("radio", { name: /^36/ });
    if (size !== null) fireEvent.click(size);
  }
  fireEvent.click(forward());
  return result;
}

async function walkToVerify(dressId?: string) {
  const result = await walkToTerms(dressId);
  fireEvent.click(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }));
  fireEvent.click(forward());
  return result;
}

function resend() {
  return screen.getByRole("button", { name: i18n.t("booking.otpResend") });
}

// The same control under either of its two labels — after a send it is cooling,
// and the wait sentence has replaced the send one.
function resendControl() {
  return screen.getByRole("button", {
    name: new RegExp(`${i18n.t("booking.otpResend")}|${i18n.t("booking.otpResendWait")}`),
  });
}

// Advancing the clock is not enough on its own. The cooldown's setTimeout is
// scheduled by an effect keyed on `cooling`, so a bare advanceTimersByTime can
// run BEFORE that effect commits — advancing past nothing, after which the timer
// is scheduled and never fires inside the test. Flushing pending effects first
// makes the timer exist before the clock moves. Locally the effect usually won
// the race anyway; on a loaded runner it does not, which is what turned this
// into a CI-only failure.
async function passCooldown() {
  await act(async () => {});
  act(() => {
    vi.advanceTimersByTime(60_000);
  });
}

function submitButton() {
  return screen.getByRole("button", { name: i18n.t("booking.submit") });
}

async function sendCode(phone = TYPED_PHONE) {
  fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), { target: { value: phone } });
  fireEvent.click(resend());
  return screen.findByLabelText(i18n.t("booking.otpCode"));
}

function enterCode(value = "123456") {
  fireEvent.change(screen.getByLabelText(i18n.t("booking.otpCode")), { target: { value } });
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  getTerms.mockResolvedValue(TERMS);
  listTypes.mockResolvedValue([appointmentType()]);
  listSlots.mockResolvedValue({ slots: SLOTS.map((starts_at) => ({ starts_at })) });
  getDress.mockResolvedValue(dressDetail());
  sendOtp.mockResolvedValue(undefined);
  verifyOtp.mockResolvedValue({
    verification_token: "vt-1",
    expires_at: "2026-08-04T07:10:00Z",
  });
  createBooking.mockResolvedValue(booking());
  paymentStatus.mockResolvedValue(payFacts());
  window.history.replaceState(null, "", "/book/slot");
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("BookPage shell", () => {
  it.each([
    ["slot", "booking.stepSlot"],
    ["details", "booking.stepDetails"],
    ["terms", "booking.stepTerms"],
    ["verify", "booking.stepOtp"],
    // R14: rendered cold, confirm has no 201 to show and may not claim one, so
    // its heading is the flow's own name rather than "the appointment is booked".
    ["confirm", "document.book"],
    // ONE static h1 over all five payment states: an h1 that changed with the
    // poll's answer would rewrite the page's own name under a screen reader.
    ["pay", "booking.payTitle"],
  ] as const)("titles the %s step with its own h1", (step, key) => {
    renderBook(step);

    // The h1 is the step, never the boutique: a static string has no state
    // where a failed fetch leaves the page untitled.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t(key));
  });

  it("marks the current step in an inert stepper", () => {
    renderBook("terms");

    const stepper = screen.getByRole("list", { name: i18n.t("booking.stepsLabel") });
    expect(within(stepper).queryAllByRole("link")).toHaveLength(0);
    expect(stepper.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
    expect(stepper.querySelector('[aria-current="step"]')).toHaveTextContent(
      i18n.t("booking.stepTerms"),
    );
  });

  it("drops the stepper on confirm — it is terminal, outside the flow", () => {
    renderBook("confirm");
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});

describe("BookPage slot step — happy paths", () => {
  it("advances to the details step with a type and a time chosen", async () => {
    renderBook();

    await pickFirstType();
    fireEvent.click(screen.getByRole("radio", { name: "10:45" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));

    expect(window.location.pathname).toBe("/book/details");
  });

  it("carries the bound dress into the forward URL on the item-based path", async () => {
    renderBook("slot", "d 1");

    await pickFirstType();
    fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));

    // Encoded exactly as api.getDress encodes it; router.tsx's decodeId is the
    // matching decoder.
    expect(window.location.pathname).toBe("/book/details/d%201");
  });

  it("opens with nothing preselected — choosing the first type would choose for her", async () => {
    listTypes.mockResolvedValue([
      appointmentType({ audience: "brides_only" }),
      appointmentType({ id: "t2", name: "חבילת כלה", duration_minutes: 120 }),
    ]);

    renderBook();

    for (const radio of await screen.findAllByRole("radio")) {
      expect(radio).not.toBeChecked();
    }
  });

  it("reads the boutique calendar, not the device — a 21:00Z slot is the NEXT day", async () => {
    listSlots.mockResolvedValue({
      slots: [{ starts_at: AUG4_1000 }, { starts_at: AUG5_0000 }],
    });

    renderBook();

    // 21:00Z is 17:00 on the 4th in New York, where the suite runs. Reading the
    // device clock would put it on the 4th at 17:00.
    expect(await screen.findByRole("radio", { name: "10:00" })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "17:00" })).toBeNull();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-05" },
    });
    expect(screen.getByRole("radio", { name: "00:00" })).toBeInTheDocument();
  });

  it("isolates every time as an LTR run inside the Hebrew page", async () => {
    renderBook();

    const chip = await screen.findByRole("radio", { name: "10:45" });
    const bdi = chip.closest("label")?.querySelector("bdi");
    expect(bdi).toHaveAttribute("dir", "ltr");
    expect(bdi).toHaveTextContent("10:45");
  });

  it("lays the grid out on one auto-fill rule — 104px minimum, no breakpoints", async () => {
    const { container } = renderBook();

    await screen.findByRole("radio", { name: "10:00" });
    const grid = container.querySelector('[class*="repeat(auto-fill"]');
    // R10: the column count is a consequence of this rule and the Card padding,
    // never a hand-set number per breakpoint.
    expect(grid?.className).toContain("repeat(auto-fill,minmax(104px,1fr))");
    expect(grid?.className).toContain("gap-2");
  });

  it("keeps the Card at --space-6 at every width", async () => {
    const { container } = renderBook();

    await screen.findByRole("radio", { name: "10:00" });
    // R9: Card hardcodes p-6 and cn has no tailwind-merge, so a caller's p-4
    // ships BOTH classes and loses on stylesheet order. Never pass one.
    const card = container.querySelector(".bg-surface.p-6");
    expect(card).not.toBeNull();
    expect(container.querySelector(".p-4")).toBeNull();
  });
});

describe("BookPage slot step — the appointment-type picker", () => {
  it("labels a brides-only type without gating it", async () => {
    listTypes.mockResolvedValue([appointmentType({ audience: "brides_only" })]);

    renderBook();

    const radio = await screen.findByRole("radio", { name: /מדידה ראשונה/ });
    expect(radio).toBeEnabled();
    expect(radio).toHaveAccessibleName(new RegExp(i18n.t("booking.audienceBrides")));

    // D10: it labels, it does not gate.
    fireEvent.click(radio);
    fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));
    expect(window.location.pathname).toBe("/book/details");
  });

  it("states each duration as an isolated numeral beside its unit", async () => {
    listTypes.mockResolvedValue([appointmentType({ duration_minutes: 90 })]);

    renderBook();

    const row = (await screen.findByRole("radio", { name: /מדידה ראשונה/ })).closest("label");
    // R19: the approved Hebrew is value-first, so the key is the bare unit and
    // the numeral is isolated at the call site. Drop the bdi and this fails.
    const bdi = row?.querySelector("bdi");
    expect(bdi).toHaveAttribute("dir", "ltr");
    expect(bdi).toHaveTextContent("90");
    expect(row).toHaveTextContent(`90 ${i18n.t("booking.typeDuration")}`);
  });

  it("reveals the deposit branch under ITS OWN row while a sibling stays bookable", async () => {
    listTypes.mockResolvedValue([
      appointmentType(),
      appointmentType({
        id: "t2",
        name: "חבילת כלה",
        duration_minutes: 120,
        deposit_required: true,
        deposit_amount_agorot: 150000,
      }),
    ]);

    renderBook();

    const deposit = await screen.findByRole("radio", { name: /חבילת כלה/ });
    fireEvent.click(deposit);

    // The reveal belongs to the row, tied by aria-describedby — never nested
    // inside the <label>, which would fold the whole panel into the accessible
    // name.
    expect(screen.getByText(new RegExp(i18n.t("booking.depositByPhone")))).toBeInTheDocument();
    expect(deposit).toHaveAccessibleDescription(new RegExp(i18n.t("booking.depositByPhone")));
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toHaveAttribute(
      "href",
      "tel:052-1234567",
    );
    // P4: through <Price>, because qa-greps.sh bans the glyph outright.
    expect(screen.getByText(/1,500/)).toBeInTheDocument();

    // The forward control is never disabled (R7); pressing it here re-announces
    // the deposit block and does nothing else.
    const forward = screen.getByRole("button", { name: i18n.t("booking.continue") });
    expect(forward).toBeEnabled();
    expect(forward).not.toHaveAttribute("aria-describedby");
    fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
    fireEvent.click(forward);
    expect(window.location.pathname).toBe("/book/slot");
    expect(document.activeElement).toBe(deposit);

    // …AND THE SIBLING STAYS BOOKABLE. This is the assertion that catches a
    // branch applied to the whole picker instead of one row.
    const sibling = screen.getByRole("radio", { name: /מדידה ראשונה/ });
    expect(sibling).toBeEnabled();
    fireEvent.click(sibling);
    expect(screen.queryByText(new RegExp(i18n.t("booking.depositByPhone")))).toBeNull();
    // The time picked while the deposit row was selected survives the switch.
    expect(screen.getByRole("radio", { name: "10:00" })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));
    expect(window.location.pathname).toBe("/book/details");
  });

  it("replaces the deposit panel with plain copy when the boutique fetch failed", async () => {
    loadBoutique.mockRejectedValue(DOWN);
    listTypes.mockResolvedValue([
      appointmentType({ deposit_required: true, deposit_amount_agorot: 150000 }),
    ]);

    renderBook();

    fireEvent.click(await screen.findByRole("radio", { name: /מדידה ראשונה/ }));

    // D12: ContactPanel with every channel absent renders an empty flex box, so
    // the degrade has to be a branch at the call site.
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });
});

describe("BookPage slot step — R7, the forward control is never disabled", () => {
  it("names both unfilled groups and moves focus to the first of them", async () => {
    renderBook();

    const forward = await screen.findByRole("button", { name: i18n.t("booking.continue") });
    expect(forward).toBeEnabled();
    fireEvent.click(forward);

    expect(screen.getByText(i18n.t("booking.typeRequired"))).toHaveAttribute("role", "alert");
    expect(screen.getByText(i18n.t("booking.timeRequired"))).toHaveAttribute("role", "alert");
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: /מדידה ראשונה/ }));
    expect(window.location.pathname).toBe("/book/slot");
  });

  it("falls through to the time group once the type is chosen", async () => {
    renderBook();

    await pickFirstType();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));

    expect(screen.queryByText(i18n.t("booking.typeRequired"))).toBeNull();
    expect(screen.getByText(i18n.t("booking.timeRequired"))).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "10:00" }));
    expect(window.location.pathname).toBe("/book/slot");
  });

  it("clears the messages once the choice is made", async () => {
    renderBook();

    fireEvent.click(await screen.findByRole("button", { name: i18n.t("booking.continue") }));
    await pickFirstType();
    fireEvent.click(screen.getByRole("radio", { name: "10:45" }));

    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("BookPage slot step — states", () => {
  it("announces the load with a visually-hidden status, never aria-busy alone", async () => {
    getTerms.mockReturnValue(pending());

    const { container } = renderBook();

    // R30: aria-busy on a plain div is announced by neither VoiceOver nor NVDA,
    // so a bride on a slow connection heard the h1, then silence.
    const status = screen.getByRole("status");
    // …and it names what is loading: catalog.loading says "the collection" on a
    // screen that loads times.
    expect(status).toHaveTextContent(i18n.t("booking.loading"));
    expect(status).not.toHaveTextContent(i18n.t("catalog.loading"));
    expect(status.closest(".sr-only")).not.toBeNull();
    expect(container.querySelectorAll(".animate-skeleton").length).toBeGreaterThan(0);
    // Nothing to advance to yet.
    expect(screen.queryByRole("button", { name: i18n.t("booking.continue") })).toBeNull();
  });

  it("replaces the flow with the phone-only entry when no terms are published", async () => {
    getTerms.mockRejectedValue(GONE);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTermsByPhone"))).toBeInTheDocument();
    // D5 is branched on the 404 at the call site, before errorMessageKey — the
    // shared helper cannot tell this NOT_FOUND from any other in the flow.
    expect(screen.queryByText(i18n.t("errors.notFound"))).toBeNull();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    // No stepper, and R12's heading: a step label above "call us" would name a
    // step that is not on the page.
    expect(screen.queryByRole("list", { name: i18n.t("booking.stepsLabel") })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("document.book"));
    expect(screen.queryByRole("button", { name: i18n.t("booking.continue") })).toBeNull();
    expect(screen.getByRole("link", { name: /קולקציה/ })).toHaveAttribute("href", "/");
  });

  it("degrades the no-terms entry to plain copy with no boutique", async () => {
    getTerms.mockRejectedValue(GONE);
    loadBoutique.mockRejectedValue(DOWN);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTermsByPhone"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });

  it("replaces the Card with the phone-only block when there are no active types", async () => {
    listTypes.mockResolvedValue([]);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTypes"))).toBeInTheDocument();
    // FINDING 4: the sentence carries no phone invitation of its own — the
    // panel beneath it does that job.
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.queryByLabelText(i18n.t("booking.pickDate"))).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("booking.continue") })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("document.book"));
  });

  it("degrades the no-types block to plain copy with no boutique", async () => {
    listTypes.mockResolvedValue([]);
    loadBoutique.mockRejectedValue(DOWN);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTypes"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
  });

  it("states the empty window as a fact — no icon, no retry, picker and date intact", async () => {
    listSlots.mockResolvedValue({ slots: [] });

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noSlots"))).toBeInTheDocument();
    // The state every new tenant ships in, so it must read as a fact, not a fault.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("catalog.retry") })).toBeNull();
    expect(screen.getByRole("radio", { name: /מדידה ראשונה/ })).toBeInTheDocument();
    expect(screen.getByLabelText(i18n.t("booking.pickDate"))).toBeInTheDocument();
  });

  it("shows the same sentence for a date inside the window with no times", async () => {
    renderBook();

    await screen.findByRole("radio", { name: "10:00" });
    // F-A5: a native date input cannot disable arbitrary dates, so she can
    // always land on an empty one. Whole-window-empty and this-date-empty are
    // the same block and the same string.
    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-06" },
    });

    expect(screen.getByText(i18n.t("booking.noSlots"))).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "10:00" })).toBeNull();
  });

  it("bounds the date control to the window the server actually returned", async () => {
    renderBook();

    const date = await screen.findByLabelText(i18n.t("booking.pickDate"));
    expect(date).toHaveValue("2026-08-04");
    expect(date).toHaveAttribute("min", "2026-08-04");
    expect(date).toHaveAttribute("max", "2026-08-05");
    expect(date).toHaveAttribute("dir", "ltr");
  });

  it("drops a time picked on another date rather than carrying it forward", async () => {
    renderBook();

    fireEvent.click(await screen.findByRole("radio", { name: "10:45" }));
    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-05" },
    });

    expect(screen.getByRole("radio", { name: "10:00" })).not.toBeChecked();
  });

  it("raises ONE muted alert with a retry when an entry read fails", async () => {
    listSlots.mockRejectedValue(DOWN);

    renderBook();

    const alerts = await screen.findAllByRole("alert");
    // One outage announced three times makes a screen reader read three
    // messages for one problem.
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toHaveTextContent(i18n.t("booking.slotsError"));
    // A backend that is down is not the boutique's fault.
    expect(alerts[0].className).toContain("text-ink-muted");
    expect(alerts[0].className).not.toContain("danger");
    expect(screen.getByRole("button", { name: i18n.t("catalog.retry") })).toBeInTheDocument();
  });

  it("re-runs every entry read from the retry button", async () => {
    listTypes.mockRejectedValueOnce(DOWN);

    renderBook();
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("catalog.retry") }));

    expect(await screen.findByRole("radio", { name: "10:00" })).toBeInTheDocument();
    expect(listTypes).toHaveBeenCalledTimes(2);
    expect(getTerms).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });

  it("says a spent budget in the load-failure block, muted, with no second key", async () => {
    listSlots.mockRejectedValue(THROTTLED);

    renderBook();

    const alert = await screen.findByRole("alert");
    // errorMessageOr already maps TOO_MANY_ATTEMPTS — do not add a second case.
    expect(alert).toHaveTextContent(i18n.t("errors.tooManyAttempts"));
    expect(alert.className).toContain("text-ink-muted");
    expect(screen.getByRole("button", { name: i18n.t("catalog.retry") })).toBeInTheDocument();
  });
});

// The two mid-flow returns land on this step from the verify step's submit
// (§6, Tasks 9-11). Their markup is the pickers' own `error` slot, so it is
// pinned here against the real Hebrew rather than waiting for the caller.
describe("BookPage slot step — the mid-flow returns", () => {
  let sheet: HTMLStyleElement;

  beforeEach(() => {
    // jsdom loads no stylesheet, so every class computes to the UA default and
    // a colour assertion would pass whichever class the line carried.
    sheet = document.createElement("style");
    sheet.textContent = `
      .text-danger { color: ${themeTokens["--color-danger"]}; }
      .text-ink-muted { color: ${themeTokens["--color-ink-muted"]}; }
      .text-warning-text { color: ${themeTokens["--color-warning-text"]}; }
    `;
    document.head.append(sheet);
  });

  afterEach(() => {
    sheet.remove();
  });

  function colourOf(className: string): string {
    const probe = document.createElement("span");
    probe.className = className;
    document.body.append(probe);
    const { color } = getComputedStyle(probe);
    probe.remove();
    return color;
  }

  it("puts errors.slotUnavailable above the time legend, in danger", () => {
    render(
      <StorefrontLayout>
        <SlotPicker
          labels={{
            pickDate: i18n.t("booking.pickDate"),
            pickTime: i18n.t("booking.pickTime"),
            noSlots: i18n.t("booking.noSlots"),
          }}
          date="2026-08-04"
          times={[{ value: AUG4_1000, label: "10:00" }]}
          value={null}
          error={i18n.t("errors.slotUnavailable")}
          onDateChange={() => undefined}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("errors.slotUnavailable"));
    // A conflict she must act on is danger; an outage is muted. Guards the
    // guard: an inert stylesheet would make both sides equal.
    expect(colourOf("text-danger")).not.toBe(colourOf("text-ink-muted"));
    expect(getComputedStyle(alert).color).toBe(colourOf("text-danger"));
    // Above the legend, not inside the fieldset — a <legend> that is not the
    // first element child stops naming its group.
    expect(alert.compareDocumentPosition(screen.getByText(i18n.t("booking.pickTime")))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  // typeGoneRepick and sizeGoneRepick are ONE semantic state — "the thing you
  // picked is gone, pick another" — so they share a register. Ruled with
  // sizeGoneRepick below: warning, not danger. Nothing she did failed.
  it("puts booking.typeGoneRepick above the picker legend, in the warning register", () => {
    render(
      <StorefrontLayout>
        <TypePicker
          types={[appointmentType()]}
          value={null}
          notice={i18n.t("booking.typeGoneRepick")}
          boutique={boutique()}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("booking.typeGoneRepick"));
    expect(colourOf("text-warning-text")).not.toBe(colourOf("text-danger"));
    expect(getComputedStyle(alert).color).toBe(colourOf("text-warning-text"));
    expect(alert.compareDocumentPosition(screen.getByText(i18n.t("booking.typeHeading")))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("keeps a real validation error on the type picker in danger", () => {
    render(
      <StorefrontLayout>
        <TypePicker
          types={[appointmentType()]}
          value={null}
          error={i18n.t("booking.typeRequired")}
          boutique={boutique()}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    expect(getComputedStyle(screen.getByRole("alert")).color).toBe(colourOf("text-danger"));
  });

  // §3.8's register table files sizeGoneRepick under --color-danger; §4.7 and
  // §5.8's measured contrast ledger both say --color-warning-text. Ruled for
  // warning: two of three agree, and the ledger is the measured accessibility
  // artifact rather than prose. Nothing she did failed — the boutique's stock
  // moved — so the chips' true validation error keeps danger and this does not.
  it("renders booking.sizeGoneRepick in the warning register, not danger", () => {
    render(
      <StorefrontLayout>
        <SizeChips
          sizes={[{ size_label: "40", available: true }]}
          value={null}
          notice={i18n.t("booking.sizeGoneRepick")}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("booking.sizeGoneRepick"));
    expect(colourOf("text-warning-text")).not.toBe(colourOf("text-danger"));
    expect(getComputedStyle(alert).color).toBe(colourOf("text-warning-text"));
  });

  it("keeps a real validation error on the size chips in danger", () => {
    render(
      <StorefrontLayout>
        <SizeChips
          sizes={[{ size_label: "40", available: true }]}
          value={null}
          error={i18n.t("booking.sizeRequired")}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    expect(getComputedStyle(screen.getByRole("alert")).color).toBe(colourOf("text-danger"));
  });
});

describe("BookPage details step", () => {
  it("advances to the terms step with a name", async () => {
    await walkToDetails();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());

    expect(window.location.pathname).toBe("/book/terms");
  });

  // The walkthrough measured `{hasForm:false, continueBtn:{type:'button',
  // insideForm:false}}` on this step: the flow was not a <form> at all, so Enter
  // in a text field did nothing and a phone keyboard's Go key was dead on the
  // last field — she had to Tab past the notes textarea AND the marketing
  // checkbox to reach «המשך».
  //
  // ⚠ THIS IS THE STRUCTURAL HALF, and it is deliberately not claimed to be the
  // behavioural one. jsdom does NOT implement implicit form submission and this
  // workspace ships no `@testing-library/user-event`, so no assertion here can
  // press Enter and watch the step advance. `e2e/storefront.spec.ts` does that
  // in a real browser; this asserts the exact three facts the walkthrough
  // recorded, on every fast test run.
  it("is a real form whose «המשך» submits it — the three facts the walkthrough measured", async () => {
    const { container } = await walkToDetails();

    const form = container.querySelector("form");
    expect(form).not.toBeNull();
    expect(forward()).toHaveAttribute("type", "submit");
    expect(forward().closest("form")).toBe(form);
    // The text field and the button are in the SAME form, which is the whole of
    // what makes implicit submission reach this step's validator.
    expect(screen.getByLabelText(i18n.t("booking.name")).closest("form")).toBe(form);
    // ⚠ `noValidate`, and it is load-bearing: the name field carries `required`
    // for AT, and native constraint validation would block the submit and show a
    // browser bubble INSTEAD of `forwardDetails` — killing the authored Hebrew,
    // the role="alert" and the focus move to the first failure in one go.
    expect(form).toHaveAttribute("novalidate");
    expect(screen.getByLabelText(i18n.t("booking.name"))).toBeRequired();
  });

  it("labels both fields visibly — a placeholder is never a label", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    expect(name).toHaveAttribute("maxLength", "80");
    expect(name).not.toHaveAttribute("placeholder");
    const notes = screen.getByLabelText(i18n.t("booking.notes"));
    expect(notes).toHaveAttribute("maxLength", "500");
    expect(notes).toHaveAccessibleDescription(new RegExp(i18n.t("booking.notesHint")));
    // The counter is on notes only: 80 characters is not a budget anyone plans
    // against, and a counter under a name reads as a rule about her name.
    expect(screen.getByText("0 / 500")).toBeInTheDocument();
  });

  it("leaves the phone field to the verify step", async () => {
    await walkToDetails();

    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    expect(screen.queryByText(i18n.t("booking.phoneHint"))).toBeNull();
  });

  it("raises nothing on input or on blur — only on the forward press", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    fireEvent.change(name, { target: { value: "" } });
    fireEvent.blur(name);
    expect(screen.queryByRole("alert")).toBeNull();

    fireEvent.click(forward());
    expect(screen.getByText(i18n.t("booking.nameRequired"))).toHaveAttribute("role", "alert");
    expect(document.activeElement).toBe(name);
    expect(window.location.pathname).toBe("/book/details");
  });

  it("blank-checks the trimmed value and length-checks the raw one", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    // Whitespace only: blank on the TRIMMED value, exactly as validation.py.
    fireEvent.change(name, { target: { value: "   " } });
    fireEvent.click(forward());
    expect(screen.getByText(i18n.t("booking.nameRequired"))).toBeInTheDocument();

    // 79 real characters between two spaces: 81 RAW, 79 trimmed. Length runs on
    // the raw value, so this is refused — a client that validated the trimmed
    // string would send 81 characters the server rejects.
    fireEvent.change(name, { target: { value: ` ${"א".repeat(79)} ` } });
    fireEvent.click(forward());
    expect(screen.getByText(i18n.t("booking.nameTooLong"))).toBeInTheDocument();
    expect(window.location.pathname).toBe("/book/details");
  });

  it("submits 80 characters of name and refuses 81 with no request issued", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    fireEvent.change(name, { target: { value: "א".repeat(81) } });
    fireEvent.click(forward());

    expect(screen.getByText(i18n.t("booking.nameTooLong"))).toBeInTheDocument();
    // The anti-vacuous half: not merely that an error rendered, but that the
    // flow issued nothing and went nowhere.
    expect(createBooking).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/book/details");

    fireEvent.change(name, { target: { value: "א".repeat(80) } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms");
  });

  it("submits 500 characters of notes and refuses 501 with no request issued", async () => {
    await walkToDetails();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    const notes = screen.getByLabelText(i18n.t("booking.notes"));
    fireEvent.change(notes, { target: { value: "א".repeat(501) } });
    fireEvent.click(forward());

    expect(screen.getByText(i18n.t("booking.notesTooLong"))).toBeInTheDocument();
    expect(createBooking).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/book/details");

    fireEvent.change(notes, { target: { value: "א".repeat(500) } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms");
  });

  it("never disables the forward control and moves focus to the first failure", async () => {
    await walkToDetails();

    const notes = screen.getByLabelText(i18n.t("booking.notes"));
    fireEvent.change(notes, { target: { value: "א".repeat(501) } });
    fireEvent.click(forward());

    // R7: it submits and fails visibly rather than stating no reason.
    expect(forward()).toBeEnabled();
    expect(screen.getByText(i18n.t("booking.nameRequired"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.notesTooLong"))).toBeInTheDocument();
    // Name is first in the form, so it is first in focus order.
    expect(document.activeElement).toBe(screen.getByLabelText(i18n.t("booking.name")));

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(document.activeElement).toBe(notes);
  });
});

// --- F20: the collection notice and the marketing consent -------------------

describe("BookPage details step — the collection notice", () => {
  it("renders the notice on the details step and on no other", async () => {
    // PPL §11(b) wants the notice at the moment of collection, and `details` is
    // that moment — it is where she types her name. The negative half is the
    // point: a notice on every step is a notice she stops reading.
    await walkToDetails();
    expect(screen.getByRole("heading", { name: i18n.t("booking.collectionNoticeHeading") }))
      .toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(
      screen.queryByRole("heading", { name: i18n.t("booking.collectionNoticeHeading") }),
    ).toBeNull();

    fireEvent.click(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }));
    fireEvent.click(forward());
    expect(
      screen.queryByRole("heading", { name: i18n.t("booking.collectionNoticeHeading") }),
    ).toBeNull();
    // And the verify step gained no control of its own.
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("renders the BOUTIQUE'S OWN notice text, not a copy of the platform default", async () => {
    // ⚠ THE ASSERTION LIVES ON THE RENDERED BLOCK, not on a backend constant.
    // `/privacy` and this block serve the SAME `privacy_notice_text` off the
    // SAME fetch (D13), so a builder who hardcoded the platform Hebrew into
    // `he.ts` "to save a prop" would publish a notice that ignores every
    // boutique's override — and every backend test would stay green.
    loadBoutique.mockResolvedValue(
      boutique({ privacy_notice_text: "הנוסח של הבוטיק עצמה על {{boutique}}." }),
    );
    await walkToDetails();

    expect(screen.getByText(/הנוסח של הבוטיק עצמה/)).toBeInTheDocument();
    expect(screen.queryByText(/הודעת ברירת מחדל/)).toBeNull();
    // Substituted, never printed raw.
    expect(screen.queryByText(/{{boutique}}/)).toBeNull();
  });

  it("renders the notice WHOLE — no clamp, no summary, no truncation", async () => {
    // ⚠ THE PROPERTY THIS SURFACE CAN ACTUALLY VOUCH FOR, and the one worth
    // holding. Whether the text discharges §11(b)(1)–(4), §13, §14 and §30A is
    // asserted against the constant in `test_privacy_text.py`, where the words
    // live; duplicating those phrases here would put a second copy of a legal
    // string in the repo — the exact failure D13 and F33's `checkin.notice`
    // comment both name — and would then be asserting that a fixture agrees
    // with itself.
    //
    // What the frontend owns is that the whole document reaches her eyes. A
    // clamped block, a "read more" disclosure or a friendly two-line summary
    // would each leave a §11 notice that is silently incomplete at the one
    // moment the statute cares about, with every backend test green.
    const notice = ["פסקה ראשונה.", "פסקה שנייה.", "פסקה שלישית."].join("\n\n");
    loadBoutique.mockResolvedValue(boutique({ privacy_notice_text: notice }));
    await walkToDetails();

    const block = screen.getByTestId("collection-notice");
    for (const paragraph of notice.split("\n\n")) {
      expect(block, `the notice is missing: ${paragraph}`).toHaveTextContent(paragraph);
    }
    // And every paragraph break survived: a single run-on block is how these
    // three would render if the pre-line handling were dropped (copy.md R1).
    expect(within(block).getAllByText(/פסקה/)).toHaveLength(3);
  });

  // The other half of the walkthrough's WCAG 1.3.1 finding. D13 makes this block
  // and `/privacy` render the SAME string off the SAME fetch, so the list
  // semantics have to be the same too — a bulleted set of rights that is a real
  // list on one screen and one undifferentiated paragraph on the other is the
  // drift D13 exists to prevent, and the §11 moment-of-collection screen is the
  // one that matters more.
  it("renders the notice's bullet run as a real list, one <li> per bullet line", async () => {
    loadBoutique.mockResolvedValue(
      boutique({
        privacy_notice_text: "מה אנחנו מבקשות:\n• שם מלא\n• מספר טלפון\n\nולמה: כדי לקבוע תור.",
      }),
    );
    await walkToDetails();

    const block = screen.getByTestId("collection-notice");
    const items = within(block).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items.map((item) => item.textContent)).toEqual(["שם מלא", "מספר טלפון"]);
    expect(within(block).getAllByRole("list")).toHaveLength(1);
    // The prose either side is untouched — the run is bounded.
    expect(within(block).getByText("מה אנחנו מבקשות:").tagName).toBe("P");
    expect(within(block).getByText("ולמה: כדי לקבוע תור.").tagName).toBe("P");
  });

  it("links out to the full document and carries no other chrome", async () => {
    await walkToDetails();

    const block = screen.getByTestId("collection-notice");
    const links = within(block).getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/privacy");
    // Not behind a disclosure: notice at the moment of collection means visible
    // at the moment of collection.
    expect(block.querySelector("details")).toBeNull();
  });
});

// The label interpolates the boutique's own name, so every lookup for it has to
// resolve the same way the component does — a bare `t()` here would search for a
// literal `{{boutique}}` and never match.
function marketingBox() {
  return screen.getByRole("checkbox", {
    name: i18n.t("booking.marketingOptIn", { boutique: "בוטיק אלמה" }),
  });
}

describe("BookPage details step — the marketing consent", () => {
  it("ships unticked", async () => {
    await walkToDetails();

    expect(marketingBox()).not.toBeChecked();
  });

  it("is the ONLY checkbox on this step, and the terms box is two steps away", async () => {
    // §30A wants the consent UNBUNDLED, and this is what unbundled means here:
    // the two boxes are not merely separate controls, they are on separate
    // screens, so neither can be ticked by a gesture aimed at the other.
    await walkToDetails();

    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(screen.queryByRole("checkbox", { name: i18n.t("booking.acceptTerms") })).toBeNull();
  });

  it("does not gate the forward control", async () => {
    // Anti-detriment: booking must not depend on it. Left alone, the flow
    // advances — which is also what makes `marketing_consent: false` on the
    // create body the common path rather than an edge case.
    await walkToDetails();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });

    fireEvent.click(forward());

    expect(window.location.pathname).toBe("/book/terms");
  });

  it("carries a ticked consent into the create body, and ticks nothing else", async () => {
    await walkToDetails();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.change(screen.getByLabelText(i18n.t("booking.notes")), {
      target: { value: "מגיעה עם אמא" },
    });
    fireEvent.click(marketingBox());
    fireEvent.click(forward());

    // The terms box is UNTOUCHED by the tick above — its own step still gates
    // the flow, so a wired-together pair would strand her here.
    expect(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") })).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }));
    fireEvent.click(forward());
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(createBooking).toHaveBeenCalledWith(
        expect.objectContaining({ marketing_consent: true }),
      );
    });
  });

  it("keeps the tick across a walk back to the slot step and forward again", async () => {
    // The flow's other answers survive a back-and-forward, and a consent that
    // silently cleared itself would be recorded as refused for a woman who gave
    // it — the one direction of that bug nobody notices.
    await walkToDetails();
    fireEvent.click(marketingBox());

    fireEvent.click(screen.getByRole("link", { name: new RegExp(i18n.t("booking.backStep")) }));
    fireEvent.click(forward());

    expect(marketingBox()).toBeChecked();
  });
});

describe("BookPage details step — the bound dress", () => {
  it("names the binding and offers every size as a radio", async () => {
    await walkToDetails("d1");

    // R19, and a BARE bdi: the dress name is owner text and may be Hebrew, so
    // forcing dir="ltr" on it would be the bidi defect, not the fix.
    const bdi = await screen.findByText("שמלת אלמה");
    expect(bdi.tagName).toBe("BDI");
    expect(bdi).not.toHaveAttribute("dir");
    expect(bdi.parentElement).toHaveTextContent(`${i18n.t("booking.forDress")} שמלת אלמה`);
    expect(screen.getByText(i18n.t("dress.sizes"))).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /^36/ })).toBeInTheDocument();
    expect(getDress).toHaveBeenCalledWith("d1");
  });

  it("keeps an unavailable size selectable and names it inside that chip", async () => {
    await walkToDetails("d1");

    const unavailable = await screen.findByRole("radio", { name: /38/ });
    // D4 + R15: the word is part of THIS radio's accessible name, not a
    // group-level sentence a screen reader never ties to the chip.
    expect(unavailable).toBeEnabled();
    expect(unavailable).toHaveAccessibleName(
      new RegExp(`38.*${i18n.t("booking.sizeUnavailable")}`, "s"),
    );
    fireEvent.click(unavailable);
    expect(unavailable).toBeChecked();

    // The longer invitation is one muted sentence under the group.
    expect(screen.getByText(i18n.t("booking.sizeUnavailableNote"))).toBeInTheDocument();
  });

  it("drops the note when every size is in the boutique", async () => {
    getDress.mockResolvedValue(
      dressDetail({ sizes: [{ size_label: "36", available: true }] }),
    );

    await walkToDetails("d1");

    await screen.findByRole("radio", { name: /^36/ });
    expect(screen.queryByText(i18n.t("booking.sizeUnavailableNote"))).toBeNull();
  });

  it("refuses to advance without a size whenever a dress is bound", async () => {
    await walkToDetails("d1");

    const size = await screen.findByRole("radio", { name: /^36/ });
    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());

    // dress_id without dress_size is a 400 at the boundary — the two are a pair.
    expect(screen.getByText(i18n.t("booking.sizeRequired"))).toHaveAttribute("role", "alert");
    expect(document.activeElement).toBe(size);
    expect(createBooking).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/book/details/d1");

    fireEvent.click(size);
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms/d1");
  });

  it("marks every size radio required", async () => {
    await walkToDetails("d1");

    for (const radio of await screen.findAllByRole("radio")) {
      expect(radio).toBeRequired();
    }
  });

  it("lets her type her name while the dress read is still in flight", async () => {
    getDress.mockReturnValue(pending());

    const { container } = await walkToDetails("d1");

    // The form is never blocked on a decoration.
    const name = screen.getByLabelText(i18n.t("booking.name"));
    fireEvent.change(name, { target: { value: "נועה" } });
    expect(name).toHaveValue("נועה");
    expect(container.querySelectorAll(".animate-skeleton").length).toBeGreaterThan(0);
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("drops the binding on a 404 and continues as a generic appointment", async () => {
    getDress.mockRejectedValue(GONE);

    await walkToDetails("d1");

    expect(await screen.findByText(i18n.t("booking.dressGoneGeneric"))).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.queryByText(i18n.t("dress.sizes"))).toBeNull();
    expect(screen.queryByText(/שמלת אלמה/)).toBeNull();

    // No size to pick, so no size is required: the generic path is a complete
    // booking, never a dead end.
    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms/d1");
  });

  it("drops the binding when the dress has no active sizes, keeping it on screen", async () => {
    getDress.mockResolvedValue(dressDetail({ sizes: [] }));

    await walkToDetails("d1");

    // Nothing failed and nothing vanished — polite, not an alert.
    const note = await screen.findByText(i18n.t("booking.dressGoneGeneric"));
    expect(note).toHaveAttribute("role", "status");
    expect(
      screen.getByText(i18n.t("booking.forDress", { dress: "שמלת אלמה" })),
    ).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("dress.sizes"))).toBeNull();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms/d1");
  });

  it("drops the binding on a non-404 failure with no retry and no error voice", async () => {
    getDress.mockRejectedValue(DOWN);

    await walkToDetails("d1");

    expect(await screen.findByText(i18n.t("booking.dressGoneGeneric"))).toBeInTheDocument();
    // A 5xx on a decoration must not stop a bride booking a fitting.
    expect(screen.queryByRole("button", { name: i18n.t("catalog.retry") })).toBeNull();
    expect(screen.queryByText(i18n.t("errors.unknown"))).toBeNull();
    expect(forward()).toBeEnabled();
  });
});

describe("BookPage terms step", () => {
  it("states the two refund numbers above the policy, in plain Hebrew", async () => {
    await walkToTerms();

    // R19: both numbers are mid-sentence, so each string is a lead and a tail
    // with the value isolated between them. The % is part of the LTR run, and
    // each numeral is its own element — remove the bdi and these two vanish.
    const hours = screen.getByText("48");
    const percent = screen.getByText("50%");
    expect(hours).toHaveAttribute("dir", "ltr");
    expect(percent).toHaveAttribute("dir", "ltr");

    const window_ = hours.parentElement as HTMLElement;
    const forfeit = percent.parentElement as HTMLElement;
    const policy = screen.getByText(TERMS.terms_text);
    expect(window_).toHaveTextContent(
      `${i18n.t("booking.refundWindow")} 48 ${i18n.t("booking.refundWindowSuffix")}`,
    );
    expect(forfeit).toHaveTextContent(
      `${i18n.t("booking.forfeit")} 50% ${i18n.t("booking.forfeitSuffix")}`,
    );

    // A paragraph is where numbers go to hide, so they sit above it.
    expect(window_.compareDocumentPosition(policy)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(forfeit.compareDocumentPosition(policy)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders the policy as text, never as HTML", async () => {
    getTerms.mockResolvedValue({ ...TERMS, terms_text: "שורה\n<b>לא תגית</b>" });

    const { container } = await walkToTerms();

    // A public, anonymous, multi-tenant surface: any HTML path here is stored
    // XSS reachable by every visitor to that tenant's storefront.
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText(/<b>לא תגית<\/b>/)).toBeInTheDocument();
  });

  it("grows the page instead of boxing the policy in its own scroller", async () => {
    await walkToTerms();

    const policy = screen.getByText(TERMS.terms_text);
    // pre-line keeps the owner's line breaks; two scroll contexts on a 375
    // phone is a trap, and a keyboard-scrollable box is a tab stop between the
    // text and the consent.
    expect(policy.className).toContain("whitespace-pre-line");
    expect(policy).toHaveAttribute("dir", "auto");
    expect(policy.className).not.toMatch(/overflow-(x|y|auto|scroll)|max-h-/);
    expect(policy).not.toHaveAttribute("tabindex");
  });

  it("refuses to advance without consent and moves focus to the checkbox", async () => {
    await walkToTerms();

    fireEvent.click(forward());

    expect(screen.getByText(i18n.t("booking.acceptRequired"))).toHaveAttribute("role", "alert");
    const consent = screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") });
    expect(document.activeElement).toBe(consent);
    expect(consent).toHaveAttribute("aria-invalid", "true");
    // A disabled forward button on a legal-consent screen states no reason.
    expect(forward()).toBeEnabled();
    expect(window.location.pathname).toBe("/book/terms");
  });

  it("advances to the verify step once consent is given", async () => {
    await walkToTerms();

    fireEvent.click(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }));
    fireEvent.click(forward());

    expect(window.location.pathname).toBe("/book/verify");
  });

  it("ties the consent to the version it was given for", async () => {
    await walkToTerms();

    const consent = screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") });
    fireEvent.click(consent);
    expect(consent).toBeChecked();

    // Walking back and forward is the same version, so it survives — the reset
    // is keyed on the version, which is what TERMS_STALE replaces.
    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));
    expect(window.location.pathname).toBe("/book/details");
    fireEvent.click(forward());
    expect(
      screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }),
    ).toBeChecked();
  });
});

describe("BookPage — step guards and the back control", () => {
  it("returns a later step entered with no picked slot to the slot step", async () => {
    renderFlow("/book/terms");

    expect(window.location.pathname).toBe("/book/slot");
    expect(await screen.findByRole("radio", { name: /מדידה ראשונה/ })).toBeInTheDocument();
  });

  it("keeps the bound dress on the way back to the slot step", () => {
    renderFlow("/book/details/d1");

    expect(window.location.pathname).toBe("/book/slot/d1");
  });

  it("exempts confirm from the guard — the booking is already written", () => {
    renderFlow("/book/confirm");

    expect(window.location.pathname).toBe("/book/confirm");
  });

  it("returns verify to the terms step when the consent was withdrawn", async () => {
    await walkToVerify();

    // Untick on the way back, then browser-forward into /book/verify. The guard
    // used to check only the slot, so submit() reached its own `=== null`
    // return: no spinner, no alert, no navigation — after an SMS was spent.
    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));
    fireEvent.click(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }));
    window.history.replaceState(null, "", "/book/verify");
    fireEvent.popState(window);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/terms");
    });
    // No errors.termsStale: nothing was republished, she withdrew her own
    // consent, and the unticked box she lands on says so.
    expect(screen.queryByText(i18n.t("errors.termsStale"))).toBeNull();
    expect(
      screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }),
    ).not.toBeChecked();
  });

  it("returns verify to the slot step when the appointment type went", async () => {
    await walkToVerify();
    await sendCode();
    enterCode();
    createBooking.mockRejectedValueOnce(GONE);
    listTypes.mockResolvedValue([appointmentType({ id: "t2", name: "מדידה שנייה" })]);

    fireEvent.click(submitButton());
    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });

    // The probe nulled typeId. Browser-forward back into verify must not park
    // her on a submit that can never fire.
    window.history.replaceState(null, "", "/book/verify");
    fireEvent.popState(window);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });
  });

  it("REPLACES on a guard redirect, so Back is not a loop back into the guard", async () => {
    renderFlow("/book/slot");
    const before = window.history.length;

    window.history.pushState(null, "", "/book/terms");
    fireEvent.popState(window);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });
    // R26 accepts a growing stack for mid-flow RECOVERY. A guard is the other
    // case: pushed, /book/confirm → Back → /book/verify → guard → /book/confirm
    // is an inescapable loop with the catalog behind it.
    expect(window.history.length).toBe(before + 1);
  });

  it("walks back one step at a time with a Link, never the history stack", async () => {
    await walkToDetails("d 1");

    const back = screen.getByRole("link", { name: i18n.t("booking.backStep") });
    expect(back).toHaveAttribute("href", "/book/slot/d%201");

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(await screen.findByRole("radio", { name: /^36/ }));
    fireEvent.click(forward());

    expect(screen.getByRole("link", { name: i18n.t("booking.backStep") })).toHaveAttribute(
      "href",
      "/book/details/d%201",
    );
  });

  it("keeps the picked slot when she walks back to it", async () => {
    await walkToDetails();

    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));

    expect(window.location.pathname).toBe("/book/slot");
    expect(screen.getByRole("radio", { name: "10:00" })).toBeChecked();
  });
});

describe("BookPage verify step — one screen that grows", () => {
  it("opens on the phone alone, as an LTR island with no placeholder", async () => {
    await walkToVerify();

    const phone = screen.getByLabelText(i18n.t("booking.phone"));
    // The label stays in the RTL flow; only the field's CONTENT direction flips,
    // so the caret rests at the physical left of the box and the value grows
    // rightwards. A Hebrew placeholder inside it would read backwards.
    expect(phone).toHaveAttribute("dir", "ltr");
    expect(phone).toHaveAttribute("inputMode", "tel");
    expect(phone).toHaveAttribute("autoComplete", "tel");
    expect(phone).not.toHaveAttribute("placeholder");
    expect(phone).toHaveAccessibleDescription(new RegExp(i18n.t("booking.phoneHint")));
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
    expect(resend()).toBeEnabled();
  });

  it("refuses a number that is not an Israeli mobile, with no request issued", async () => {
    await walkToVerify();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: "0212345" },
    });
    fireEvent.click(resend());

    expect(screen.getByText(i18n.t("booking.phoneInvalid"))).toHaveAttribute("role", "alert");
    expect(sendOtp).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText(i18n.t("booking.phone")));
  });

  it("appends the code field below the phone, which never leaves the screen", async () => {
    await walkToVerify();

    const code = await sendCode();

    expect(sendOtp).toHaveBeenCalledWith(WIRE_PHONE);
    // A mistyped number is the commonest OTP failure, and she can only SEE it if
    // the number is still on screen — so the form grows, it never swaps.
    expect(screen.getByLabelText(i18n.t("booking.phone"))).toHaveValue(TYPED_PHONE);
    await expectFocus(code);
    // R16: otpSent is the field's help text, spoken once by aria-describedby as
    // focus arrives. A live region here would double-announce it.
    expect(code).toHaveAccessibleDescription(new RegExp(i18n.t("booking.otpSent")));
    expect(screen.queryByText(i18n.t("booking.otpSent"))).not.toHaveAttribute("role", "status");
  });

  // --- the pending intent must survive a render it did not ask for ---------
  //
  // The step defers its focus moves to the effect below the render that mounts
  // the target, because the code field and the dead-end block do not exist when
  // send() decides on them. That effect CLEARS the intent before it knows the
  // focus landed, so a render that commits in between discards the move for
  // good: node?.focus() no-ops on a ref that is still null, and nothing tries
  // again.
  //
  // React runs passive effects in a task of their own, after paint, so in a
  // browser a response can land in that gap — see inPaintGap. act() has no such
  // gap, which is why the defect passes every other test in this file.
  //
  // `phone` is deliberately not covered: its field is mounted in every render
  // the verify form has, so an early flush moves the focus early rather than
  // losing it. Nothing to reproduce.

  it("keeps the code field's focus when the send lands in the gap after a paint", async () => {
    // The layout's boutique read is the paint: it is in flight on entry to the
    // flow and settles whenever the network says so — here, one microtask
    // before the send it has nothing to do with.
    const boutiqueRead = deferred<BoutiqueResponse>();
    loadBoutique.mockReturnValue(boutiqueRead.promise);
    const sent = deferred<undefined>();
    sendOtp.mockReturnValue(sent.promise);

    await walkToVerify();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: TYPED_PHONE },
    });
    fireEvent.click(resend());

    await inPaintGap(
      () => {
        boutiqueRead.settle(boutique());
      },
      () => {
        sent.settle(undefined);
      },
    );

    // expectFocus, not a bare read: against the FIXED code the move genuinely is
    // later — it lands on the commit that mounts the field — so a runner too
    // loaded to drain the flush inside the gap's settle would fail on timing
    // alone. Polling cannot rescue the defect this pins: a discarded intent
    // never fires, so the unfixed code spends the whole timeout and still goes
    // red. And expectFocus re-reads strictly after settling, so a later commit
    // taking the focus away again is still caught.
    // ⚠ findBy, not getBy. The argument is evaluated BEFORE expectFocus is
    // entered, so a synchronous get here races the field's own mount rather than
    // its focus — and under the concurrent gate it lost, throwing «Unable to
    // find a label» from the selector instead of failing on focus. expectFocus
    // still does its strict re-read, so nothing is weakened.
    await expectFocus(await screen.findByLabelText(i18n.t("booking.otpCode")));
  });

  it("keeps the dead end's focus when the 429 lands in the gap after a paint", async () => {
    // The costliest one to lose: the form is REPLACED, so focus is left on a
    // control that no longer exists and a screen reader hears nothing about the
    // exit she was just given.
    const boutiqueRead = deferred<BoutiqueResponse>();
    loadBoutique.mockReturnValue(boutiqueRead.promise);
    let refuse: () => void = () => undefined;
    sendOtp.mockReturnValue(
      new Promise<void>((_resolve, reject) => {
        refuse = () => {
          reject(THROTTLED);
        };
      }),
    );

    await walkToVerify();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: TYPED_PHONE },
    });
    fireEvent.click(resend());

    await inPaintGap(
      () => {
        boutiqueRead.settle(boutique());
      },
      () => {
        refuse();
      },
    );

    // findBy for the same reason as the send-gap test above: the dead end has to
    // exist before its focus can be asserted, and the get raced its mount.
    const deadEnd = await screen.findByText(i18n.t("errors.otpSendBudget"));
    await expectFocus(deadEnd.closest("[tabindex]"));
  });

  // The other half of the contract above. Keeping an intent alive until its node
  // exists is only safe while the node is still the one she asked for; an intent
  // that outlives that is a focus STEAL waiting for a re-mount.
  it("drops the code intent when she edits the phone while the send is in flight", async () => {
    const sent = deferred<undefined>();
    sendOtp.mockReturnValue(sent.promise);

    await walkToVerify();
    const phone = screen.getByLabelText(i18n.t("booking.phone"));
    fireEvent.change(phone, { target: { value: TYPED_PHONE } });
    fireEvent.click(resend());

    // The field carries no `disabled`, so typing through the ~1s SMS round trip
    // is an ordinary thing to do — a stray digit, a correction.
    fireEvent.change(phone, { target: { value: `${TYPED_PHONE}8` } });
    await act(async () => {
      sent.settle(undefined);
    });

    // codeSentFor is the number send() captured, and the live phone is not it —
    // so the code field never mounted and the "code" intent has no target.
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();

    // She fixes the typo. The field appears, and must NOT pull focus out of the
    // input she is typing in (WCAG 3.2.2 — no change of context on input).
    phone.focus();
    fireEvent.change(phone, { target: { value: TYPED_PHONE } });
    await screen.findByLabelText(i18n.t("booking.otpCode"));

    expect(document.activeElement).toBe(phone);
  });

  it("keeps the code in ONE field — no six-box widget at any width", async () => {
    await walkToVerify();

    const code = await sendCode();

    expect(code).toHaveAttribute("dir", "ltr");
    expect(code).toHaveAttribute("inputMode", "numeric");
    expect(code).toHaveAttribute("autoComplete", "one-time-code");
    expect(code).toHaveAttribute("maxLength", "6");
    // autocomplete="one-time-code" fills a SINGLE field; against split fields
    // several browsers drop the whole code into box 1 and stop.
    expect(screen.getAllByRole("textbox")).toHaveLength(2);
  });

  it("filters the code to six digits", async () => {
    await walkToVerify();

    const code = await sendCode();
    fireEvent.change(code, { target: { value: "12 34-56789" } });

    expect(code).toHaveValue("123456");
  });

  it("collapses the code field when she edits the number it was minted for", async () => {
    await walkToVerify();

    await sendCode();
    enterCode();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: "0509999999" },
    });

    // A code minted for number A cannot verify number B, and submitting it would
    // spend a verify budget to learn nothing.
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
    // The cooldown survives the collapse: it is a property of the last send, not
    // of the sub-state.
    expect(resendControl()).toBeDisabled();
  });

  it("swaps the resend label for a wait sentence that carries no number", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      await walkToVerify();
      await sendCode();

      const waiting = screen.getByRole("button", { name: i18n.t("booking.otpResendWait") });
      // R3: no ticking value, so the label itself has to be the explanation —
      // `disabled` drops the control from the tab order, which makes any
      // aria-describedby on it inert.
      expect(waiting).toBeDisabled();
      expect(waiting.textContent).not.toMatch(/\d/);
      expect(screen.queryByRole("timer")).toBeNull();

      await passCooldown();

      await waitFor(() => {
        expect(resend()).toBeEnabled();
      });
      // The one discrete event in the cooldown: the button becoming available.
      expect(screen.getByRole("status")).toHaveTextContent(i18n.t("booking.otpResend"));
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("BookPage verify step — the dead ends", () => {
  it("replaces the form with the send-budget block on a 429", async () => {
    sendOtp.mockRejectedValue(THROTTLED);

    await walkToVerify();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: TYPED_PHONE },
    });
    fireEvent.click(resend());

    const block = await screen.findByText(i18n.t("errors.otpSendBudget"));
    // The /otp/send budget is 5 per HOUR, so errors.tooManyAttempts ("try again
    // in a moment") would be a lie that makes her hammer the same 429.
    expect(screen.queryByText(i18n.t("errors.tooManyAttempts"))).toBeNull();
    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    // Reached BY a focus move, so it is deliberately not an assertive region.
    expect(screen.queryByRole("alert")).toBeNull();
    await expectFocus(block.closest("[tabindex]"));
    // The h1 and the way back both stay: she is not trapped.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("booking.stepOtp"));
    expect(screen.getByRole("link", { name: i18n.t("booking.backStep") })).toBeInTheDocument();
  });

  it("replaces the form with the phone-only exit on SMS_NOT_CONFIGURED", async () => {
    sendOtp.mockRejectedValue(new ApiError(503, "SMS_NOT_CONFIGURED", "no provider"));

    await walkToVerify();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: TYPED_PHONE },
    });
    fireEvent.click(resend());

    // Known at boot and permanent — this is the one that really has no way back.
    expect(await screen.findByText(i18n.t("errors.smsUnavailable"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
  });

  it("keeps the form alive on SMS_UNAVAILABLE — a failed send is transient", async () => {
    sendOtp.mockRejectedValueOnce(new ApiError(503, "SMS_UNAVAILABLE", "provider blip"));

    await walkToVerify();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: TYPED_PHONE },
    });
    fireEvent.click(resend());

    // Rule 10 holds — the same STRING as SMS_NOT_CONFIGURED, because which of
    // the two fired is the boutique's problem and not hers. What changes is the
    // shape: the dead end is never cleared while BookPage stays mounted, so
    // routing one failed provider send there ended the session permanently.
    const alert = await screen.findByText(i18n.t("errors.smsUnavailable"));
    expect(alert).toHaveAttribute("role", "alert");
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.getByLabelText(i18n.t("booking.phone"))).toHaveValue(TYPED_PHONE);

    fireEvent.click(resend());
    expect(await screen.findByLabelText(i18n.t("booking.otpCode"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("errors.smsUnavailable"))).toBeNull();
  });

  it("stops lying after the send budget and offers the phone instead", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      await walkToVerify();
      fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
        target: { value: TYPED_PHONE },
      });

      // Five is the per-phone hourly budget. Past it the server answers a real
      // send and a spent budget with the SAME silent 204 — deliberately, so the
      // endpoint is not an oracle — so a sixth "code sent" would be false.
      for (let attempt = 0; attempt < 5; attempt++) {
        // Wait for the cooldown to actually lift before clicking. A click on the
        // still-disabled control is silently a no-op, so racing it here does not
        // fail the loop — it just sends one fewer code and fails the count below,
        // which is exactly how this read as "4 instead of 5" on CI.
        await waitFor(() => {
          expect(resendControl()).toBeEnabled();
        });
        fireEvent.click(resendControl());
        await screen.findByLabelText(i18n.t("booking.otpCode"));
        await passCooldown();
      }
      await waitFor(() => {
        expect(sendOtp).toHaveBeenCalledTimes(5);
      });

      await waitFor(() => {
        expect(resendControl()).toBeEnabled();
      });
      fireEvent.click(resendControl());

      const block = await screen.findByText(i18n.t("errors.otpSendBudget"));
      expect(sendOtp).toHaveBeenCalledTimes(5);
      expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
      await expectFocus(block.closest("[tabindex]"));
    } finally {
      vi.useRealTimers();
    }
  });

  it("degrades the dead end to plain copy when the boutique fetch failed", async () => {
    loadBoutique.mockRejectedValue(DOWN);
    sendOtp.mockRejectedValue(new ApiError(503, "SMS_UNAVAILABLE", "sms down"));

    await walkToVerify();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: TYPED_PHONE },
    });
    fireEvent.click(resend());

    // The worst cell in the flow: no way forward AND no contactable exit. It at
    // least says so rather than rendering an empty panel.
    expect(await screen.findByText(i18n.t("errors.smsUnavailable"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });
});

describe("BookPage verify step — submit", () => {
  it("verifies, books and lands on the confirmation", async () => {
    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm");
    });
    // ONE normalisation, three calls. Any divergence between them answers
    // PHONE_NOT_VERIFIED for a correct code.
    expect(verifyOtp).toHaveBeenCalledWith(WIRE_PHONE, "123456");
    expect(createBooking).toHaveBeenCalledWith({
      phone: WIRE_PHONE,
      verification_token: "vt-1",
      name: "נועה",
      appointment_type_id: "t1",
      starts_at: AUG4_1000,
      terms_version: 3,
      dress_id: null,
      dress_size: null,
      notes: "מגיעה עם אמא",
      // F20 / §30A. DEFAULT OFF, and this exhaustive body is where that is
      // actually pinned: `walkToTerms` never touches the marketing box, so a
      // checkbox that shipped pre-ticked — or one whose value was wired to
      // `accepted` — reddens here rather than in a test about consent.
      marketing_consent: false,
    });
  });

  it("sends the bound dress and its size as the pair the backend requires", async () => {
    createBooking.mockResolvedValue(booking({ dress_name: "שמלת אלמה", dress_size: "36" }));

    await walkToVerify("d1");
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm/d1");
    });
    expect(createBooking).toHaveBeenCalledWith(
      expect.objectContaining({ dress_id: "d1", dress_size: "36" }),
    );
  });

  it("submits once for a double tap and keeps the button's own label", async () => {
    const gate = deferred<BookingCreateResponse>();
    createBooking.mockReturnValue(gate.promise);

    await walkToVerify();
    await sendCode();
    enterCode();
    const submit = submitButton();
    fireEvent.click(submit);
    fireEvent.click(submit);

    await waitFor(() => {
      expect(submit).toHaveAttribute("aria-busy", "true");
    });
    // React commits `disabled` asynchronously, so the handler's own guard is the
    // layer that catches a fast double tap on iOS.
    expect(verifyOtp).toHaveBeenCalledTimes(1);
    expect(createBooking).toHaveBeenCalledTimes(1);
    // F-C6: swapping children to booking.submitting re-sizes the invisible label
    // and the width jumps — the one thing the loading variant exists to prevent.
    expect(submit).toHaveTextContent(i18n.t("booking.submit"));
    expect(screen.getByRole("status")).toHaveTextContent(i18n.t("booking.submitting"));
    // The fields stay typeable: the payload was captured at submit time.
    expect(screen.getByLabelText(i18n.t("booking.phone"))).toBeEnabled();

    gate.settle(booking());
    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm");
    });
  });

  it("keeps a wrong code on screen, selected, with resend still reachable", async () => {
    verifyOtp.mockRejectedValue(OTP_WRONG);

    await walkToVerify();
    await sendCode();
    enterCode("111111");
    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("errors.otpInvalid"))).toHaveAttribute("role", "alert");
    const code = screen.getByLabelText(i18n.t("booking.otpCode"));
    // Clearing it destroys the evidence of what she typed.
    expect(code).toHaveValue("111111");
    await expectFocus(code);
    // A burnt code is indistinguishable from a wrong one, so the only working
    // remedy must stay visible directly below the field.
    expect(resendControl()).toBeInTheDocument();
    expect(createBooking).not.toHaveBeenCalled();
  });

  it("names resend as the remedy for an expired code", async () => {
    verifyOtp.mockRejectedValue(OTP_STALE);

    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    // OTP_TTL_SECONDS is 300 and starts ticking at /otp/send — a bride who took
    // six minutes to find her phone needs a resend, not a retype.
    expect(await screen.findByText(i18n.t("errors.otpExpired"))).toBeInTheDocument();
    expect(screen.getByLabelText(i18n.t("booking.otpCode"))).toHaveValue("123456");
    expect(resendControl()).toBeInTheDocument();
  });

  it("leaves the whole form intact on a verify-face 429", async () => {
    verifyOtp.mockRejectedValue(THROTTLED);

    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    // 10 per 5 minutes — the window is short and self-clearing, so "try again in
    // a moment" is true here and both controls stay enabled.
    const alert = await screen.findByText(i18n.t("errors.tooManyAttempts"));
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert.className).toContain("text-ink-muted");
    expect(screen.getByLabelText(i18n.t("booking.otpCode"))).toBeInTheDocument();
    await waitFor(() => {
      expect(submitButton()).toBeEnabled();
    });
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });

  it("collapses to the phone on PHONE_NOT_VERIFIED and keeps every answer", async () => {
    createBooking.mockRejectedValue(TOKEN_DEAD);

    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    const alert = await screen.findByText(i18n.t("errors.phoneNotVerified"));
    expect(alert).toHaveAttribute("role", "alert");
    // The token died; the code it minted is worthless, so it goes.
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
    const phone = screen.getByLabelText(i18n.t("booking.phone"));
    expect(phone).toHaveValue(TYPED_PHONE);
    await expectFocus(phone);

    // A restart of IDENTITY is not a restart of INTENT: re-typing 500 characters
    // of "coming with my mother" to fix an OTP is the dead end this feature
    // exists to remove. Consent included — the version did not change.
    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));
    expect(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") })).toBeChecked();
    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));
    expect(screen.getByLabelText(i18n.t("booking.name"))).toHaveValue("נועה");
    expect(screen.getByLabelText(i18n.t("booking.notes"))).toHaveValue("מגיעה עם אמא");
    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));
    expect(screen.getByRole("radio", { name: "10:00" })).toBeChecked();
  });

  it("R13 — re-enables submit over a contactable exit and retries on the live token", async () => {
    createBooking.mockRejectedValueOnce(new ApiError(500, "UNKNOWN", "boom"));

    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    // Without this row a bride who verified, accepted the policy and pressed
    // commit gets a spinner that stops and no way to learn whether she is booked.
    const alert = await screen.findByText(i18n.t("errors.unknown"));
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert.className).toContain("text-ink-muted");
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    await waitFor(() => {
      expect(submitButton()).toBeEnabled();
    });

    // Retry is safe: create_booking rolls the whole transaction back, so the
    // verification token survives and must NOT be re-minted.
    fireEvent.click(submitButton());
    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm");
    });
    expect(verifyOtp).toHaveBeenCalledTimes(1);
    expect(createBooking).toHaveBeenCalledTimes(2);
  });

  it("keeps the verification when a digit is deleted and retyped", async () => {
    createBooking.mockRejectedValueOnce(BROKEN);

    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());
    await screen.findByText(i18n.t("errors.unknown"));

    // A transient touch of the field: same number out, same number back in.
    const phone = screen.getByLabelText(i18n.t("booking.phone"));
    fireEvent.change(phone, { target: { value: TYPED_PHONE.slice(0, -1) } });
    fireEvent.change(phone, { target: { value: TYPED_PHONE } });
    enterCode();
    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm");
    });
    // Discarding the token here bought nothing — consume_verification
    // predicates on the phone, so a token minted for A cannot book B — and cost
    // her the booking: the re-verify hits a row whose consumed_at is already
    // set, answers OTP_INVALID, and tells her that her correct code is wrong.
    expect(verifyOtp).toHaveBeenCalledTimes(1);
  });
});

// State 14: every designed submit failure routed to the step that owns its
// recovery, AHEAD of the R13 catch-all — which must still catch everything
// else. Her verification token survives all of them (§6.12), so none of these
// paths re-mints one.
describe("BookPage — the error-recovery matrix", () => {
  async function readyToSubmit(dressId?: string) {
    const result = await walkToVerify(dressId);
    await sendCode();
    enterCode();
    return result;
  }

  it("re-fetches the grid and clears the taken time on SLOT_UNAVAILABLE", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(SLOT_TAKEN);
    listSlots.mockResolvedValue({ slots: [{ starts_at: AUG4_1045 }, { starts_at: AUG4_1130 }] });

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });
    expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("errors.slotUnavailable"));
    // "אלה המועדים הפנויים המעודכנים" is only true of a grid that was re-read.
    expect(listSlots).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("radio", { name: "11:30" })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "10:00" })).toBeNull();
    expect(screen.getByRole("radio", { name: "10:45" })).not.toBeChecked();
    // A lost race is not a restart of intent: the type and the date survive.
    expect(screen.getByRole("radio", { name: /מדידה ראשונה/ })).toBeChecked();
    expect(screen.getByLabelText(i18n.t("booking.pickDate"))).toHaveValue("2026-08-04");
    expect(verifyOtp).toHaveBeenCalledTimes(1);
    expect(createBooking).toHaveBeenCalledTimes(1);
  });

  it("re-fetches the policy and resets the consent on TERMS_STALE", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(TERMS_MOVED);
    getTerms.mockResolvedValue({
      version: 4,
      terms_text: "מדיניות מעודכנת: ביטול עד 72 שעות.",
      refundable_until_hours_before: 72,
      forfeit_percent: 25,
    });

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/terms");
    });
    expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("errors.termsStale"));
    expect(getTerms).toHaveBeenCalledTimes(2);
    expect(screen.getByText("מדיניות מעודכנת: ביטול עד 72 שעות.")).toBeInTheDocument();
    expect(screen.queryByText(TERMS.terms_text)).toBeNull();
    expect(screen.getByText("72").parentElement).toHaveTextContent(
      `${i18n.t("booking.refundWindow")} 72 ${i18n.t("booking.refundWindowSuffix")}`,
    );
    // Consent is consent to a VERSION. Carrying it forward would record
    // agreement to text she never saw — the whole reason terms_version is sent.
    expect(
      screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }),
    ).not.toBeChecked();
  });

  it("adopts the phone-only entry when the policy was deleted outright", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(TERMS_MOVED);
    getTerms.mockRejectedValue(GONE);

    fireEvent.click(submitButton());

    // F13 cannot accept a booking with no terms version, so the flow cannot
    // complete: the same D5 state, reached from a second trigger point.
    expect(await screen.findByText(i18n.t("booking.noTermsByPhone"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: i18n.t("booking.stepsLabel") })).toBeNull();
  });

  it("degrades that phone-only entry to plain copy when the boutique fetch failed", async () => {
    loadBoutique.mockRejectedValue(DOWN);
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(TERMS_MOVED);
    getTerms.mockRejectedValue(GONE);

    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("booking.noTermsByPhone"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });

  it("leaves her on verify when the policy re-fetch itself fails", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(TERMS_MOVED);
    getTerms.mockRejectedValue(DOWN);

    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("errors.unknown"))).toHaveAttribute("role", "alert");
    expect(window.location.pathname).toBe("/book/verify");
    expect(screen.getByLabelText(i18n.t("booking.otpCode"))).toHaveValue("123456");
    await waitFor(() => {
      expect(submitButton()).toBeEnabled();
    });
  });

  it("probes NOT_FOUND back to the type picker when the type went", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(GONE);
    listTypes.mockResolvedValue([appointmentType({ id: "t2", name: "מדידה שנייה" })]);

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });
    expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("booking.typeGoneRepick"));
    expect(listTypes).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("radio", { name: /מדידה שנייה/ })).not.toBeChecked();
    expect(screen.queryByRole("radio", { name: /מדידה ראשונה/ })).toBeNull();
    // Only the two reads that can answer "which of the three vanished".
    expect(listSlots).toHaveBeenCalledTimes(1);
    expect(getDress).not.toHaveBeenCalled();
    expect(screen.getByRole("radio", { name: "10:00" })).toBeChecked();
  });

  it("probes NOT_FOUND back to the size chips when the type and dress both stand", async () => {
    await readyToSubmit("d1");
    createBooking.mockRejectedValueOnce(GONE);
    getDress.mockResolvedValue(dressDetail({ sizes: [{ size_label: "40", available: true }] }));

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/details/d1");
    });
    expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("booking.sizeGoneRepick"));
    expect(getDress).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("radio", { name: /^40/ })).not.toBeChecked();
    expect(screen.queryByRole("radio", { name: /^36/ })).toBeNull();
    // The boutique's stock moved, not her mind: her own answers are untouched.
    expect(screen.getByLabelText(i18n.t("booking.name"))).toHaveValue("נועה");
    expect(screen.getByLabelText(i18n.t("booking.notes"))).toHaveValue("מגיעה עם אמא");
    expect(createBooking).toHaveBeenCalledTimes(1);
  });

  it("drops the binding and re-issues the booking exactly once when the dress went", async () => {
    await readyToSubmit("d1");
    createBooking.mockRejectedValueOnce(GONE);
    getDress.mockRejectedValueOnce(GONE);

    fireEvent.click(submitButton());

    // R20: the spec's words are "drop the binding and CONTINUE". Walking her
    // back two steps for a decoration she did not choose costs three
    // navigations against a 600-second token already partly spent.
    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm/d1");
    });
    expect(screen.getByText(i18n.t("booking.dressGoneGeneric"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.confirmKeepScreen"))).toBeInTheDocument();
    // F16's one-string change (booking.md:1823, pre-decided #3): the screen
    // stops claiming to be her ONLY record, because a confirmation SMS now
    // exists — and it may not promise one in any tense, because at F16 ship time
    // no provider is configured and kosher phones never receive SMS at all. The
    // screenshot nudge STAYS for exactly those customers.
    const keep = i18n.t("booking.confirmKeepScreen");
    expect(keep).not.toContain("היחיד");
    expect(keep).toContain("לצלם את המסך");
    expect(keep).not.toMatch(/נשלח|נשלחה|נשלח לך|הודעה|SMS/);
    expect(createBooking).toHaveBeenCalledTimes(2);
    expect(createBooking).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        dress_id: null,
        dress_size: null,
        // The token survived the failed claim; re-minting one would burn a send.
        verification_token: "vt-1",
      }),
    );
    expect(verifyOtp).toHaveBeenCalledTimes(1);
  });

  it("keeps the submit button loading while the probe reads", async () => {
    const gate = deferred<AppointmentTypeRow[]>();
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(GONE);
    listTypes.mockReturnValue(gate.promise);

    const submit = submitButton();
    fireEvent.click(submit);

    await waitFor(() => {
      expect(listTypes).toHaveBeenCalledTimes(2);
    });
    // R20: the probe is part of the submit, not a second interaction.
    expect(submit).toHaveAttribute("aria-busy", "true");
    expect(window.location.pathname).toBe("/book/verify");

    gate.settle([appointmentType({ id: "t2", name: "מדידה שנייה" })]);
    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });
  });

  it("leaves everything intact on verify when the probe itself is throttled", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(GONE);
    listTypes.mockRejectedValueOnce(THROTTLED);

    fireEvent.click(submitButton());

    // Realistic: every read shares the per-tenant throttle. R20 routes this to
    // the R13 face rather than guessing which of the three vanished.
    expect(await screen.findByText(i18n.t("errors.unknown"))).toHaveAttribute("role", "alert");
    expect(window.location.pathname).toBe("/book/verify");
    expect(screen.getByLabelText(i18n.t("booking.otpCode"))).toHaveValue("123456");
    expect(screen.getByLabelText(i18n.t("booking.phone"))).toHaveValue(TYPED_PHONE);
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("booking.typeGoneRepick"))).toBeNull();
    await waitFor(() => {
      expect(submitButton()).toBeEnabled();
    });
  });

  it("falls back to R13 when the probe finds nothing missing", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(GONE);

    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("errors.unknown"))).toBeInTheDocument();
    expect(window.location.pathname).toBe("/book/verify");
    expect(getDress).not.toHaveBeenCalled();
    expect(createBooking).toHaveBeenCalledTimes(1);
  });

  it("routes a rejected body back to the details step, never into R13", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(
      new ApiError(400, "VALIDATION_ERROR", "name contains invalid characters"),
    );

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/details");
    });
    // R13's "try again" is a permanent dead end for a deterministically
    // rejected body: every press re-sends the same bytes and spends another
    // slot of a 10-per-hour create budget.
    expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("errors.validation"));
    expect(screen.queryByText(i18n.t("errors.unknown"))).toBeNull();
    // Everything she typed survives the return — this is a fix, not a restart.
    expect(screen.getByLabelText(i18n.t("booking.name"))).toHaveValue("נועה");
  });

  it("names a spent create budget instead of telling her to try again", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(THROTTLED);

    fireEvent.click(submitButton());

    // The window is about an hour, so R13's "נסי שוב" would put her on a button
    // that cannot work for that long. Its own key, with a phone number under it.
    const alert = await screen.findByText(i18n.t("errors.bookingBudget"));
    expect(alert).toHaveAttribute("role", "alert");
    expect(screen.queryByText(i18n.t("errors.unknown"))).toBeNull();
    expect(screen.queryByText(i18n.t("errors.tooManyAttempts"))).toBeNull();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/book/verify");
  });

  it("keeps R13 as the final fallback for an undiagnosable failure", async () => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(BROKEN);

    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("errors.unknown"))).toHaveAttribute("role", "alert");
    expect(window.location.pathname).toBe("/book/verify");
    // None of the routed branches may claim a failure they cannot diagnose.
    expect(screen.queryByText(i18n.t("errors.slotUnavailable"))).toBeNull();
    expect(screen.queryByText(i18n.t("errors.termsStale"))).toBeNull();
    expect(screen.queryByText(i18n.t("booking.typeGoneRepick"))).toBeNull();
    expect(screen.queryByText(i18n.t("booking.sizeGoneRepick"))).toBeNull();
    expect(screen.queryByText(i18n.t("booking.dressGoneGeneric"))).toBeNull();
    // And no read is spent probing a code that carries no cause.
    expect(listSlots).toHaveBeenCalledTimes(1);
    expect(listTypes).toHaveBeenCalledTimes(1);
    expect(getTerms).toHaveBeenCalledTimes(1);
  });

  it("degrades the R13 exit to plain copy when the boutique fetch failed", async () => {
    loadBoutique.mockRejectedValue(DOWN);
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(BROKEN);

    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("errors.unknown"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });
});

describe("BookPage confirmation", () => {
  async function book(overrides: Partial<BookingCreateResponse> = {}, dressId?: string) {
    createBooking.mockResolvedValue(booking(overrides));
    const result = await walkToVerify(dressId);
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());
    await screen.findByText(i18n.t("booking.confirmKeepScreen"));
    return result;
  }

  it("states the appointment in full, in the boutique's zone", async () => {
    await book();

    expect(screen.getByText(i18n.t("booking.confirmWhen"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.confirmWhat"))).toBeInTheDocument();
    // The suite's clock is America/New_York; 07:00Z is 03:00 there and 10:00 in
    // Jerusalem. She must read the boutique's time, not her device's.
    expect(screen.getByText(/יום שלישי/)).toBeInTheDocument();
    const islands = screen.getAllByText(/^(4\.8\.2026|10:00)$/);
    expect(islands).toHaveLength(2);
    for (const island of islands) {
      expect(island.tagName).toBe("BDI");
      expect(island).toHaveAttribute("dir", "ltr");
    }
    expect(screen.getByText("מדידה ראשונה")).toBeInTheDocument();
    // §7.3: status is server-constant on this path, so printing it invites the
    // reader to wonder what the other values are.
    expect(screen.queryByText(/confirmed/)).toBeNull();
    // §7.5: the words and the stated facts are the success signal, not a colour.
    expect(document.querySelector(".text-success, .bg-success")).toBeNull();
  });

  it("names the boutique in the title, isolated, falling back to the nameless one", async () => {
    await book();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(`${i18n.t("booking.confirmTitleNamed")}בוטיק אלמה`);
    // R19's highest-risk instance: a free-text tenant name inside the h1 of her
    // only record. Bare bdi — the name may be Hebrew or Latin.
    const bdi = heading.querySelector("bdi");
    expect(bdi).not.toHaveAttribute("dir");
    expect(bdi).toHaveTextContent("בוטיק אלמה");
  });

  it("drops the name rather than printing the generic fallback on her only record", async () => {
    loadBoutique.mockRejectedValue(DOWN);

    await book();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(i18n.t("booking.confirmTitle"));
    expect(heading).not.toHaveTextContent(i18n.t("catalog.essenceFallback"));
  });

  it("prints the dress line on the item path and no empty row on the generic one", async () => {
    await book({ dress_name: "שמלת אלמה", dress_size: "36" }, "d1");

    // R19: two owner-authored values on one line, each in its own bare bdi.
    const line = screen.getByText("36").parentElement as HTMLElement;
    expect(line).toHaveTextContent(`שמלת אלמה · ${i18n.t("booking.confirmDress")} 36`);
    const [dressBdi, sizeBdi] = line.querySelectorAll("bdi");
    expect(dressBdi).toHaveTextContent("שמלת אלמה");
    expect(dressBdi).not.toHaveAttribute("dir");
    expect(sizeBdi).toHaveTextContent("36");
    expect(sizeBdi).not.toHaveAttribute("dir");
  });

  it("omits the dress line entirely when nothing is bound", async () => {
    await book();

    expect(screen.queryByText(/מידה/)).toBeNull();
  });

  it("renders the cold load as a short true statement, never a claim it cannot back", async () => {
    renderFlow("/book/confirm");

    // D6 tells her to screenshot, and on iOS a screenshot is an app-switch that
    // can reload the tab — this branch is the one that instruction causes.
    expect(await screen.findByText(i18n.t("booking.confirmCold"))).toBeInTheDocument();
    expect(window.location.pathname).toBe("/book/confirm");
    // R14: no warm title over a booking it has no evidence for.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("document.book"));
    expect(screen.queryByText(i18n.t("booking.confirmTitle"))).toBeNull();
    // F-C8: "keep this screen" above a screen holding no appointment instructs
    // her to preserve an absence.
    expect(screen.queryByText(i18n.t("booking.confirmKeepScreen"))).toBeNull();
    expect(screen.queryByText(i18n.t("booking.confirmWhen"))).toBeNull();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("booking.backToCatalog") })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("replaces the cold panel with plain copy when the boutique fetch failed", async () => {
    loadBoutique.mockRejectedValue(DOWN);

    renderFlow("/book/confirm");

    expect(await screen.findByText(i18n.t("booking.confirmCold"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });

  it("forwards verify to confirm once the booking is written, never to slot", async () => {
    await book();

    window.history.replaceState(null, "", "/book/verify");
    fireEvent.popState(window);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/confirm");
    });
    expect(screen.getByText(i18n.t("booking.confirmKeepScreen"))).toBeInTheDocument();
  });
});

// The deposit hand-off. Five states, and the one most likely to be forgotten is
// the sixth thing here: what she sees when the bounded poll runs out WITHOUT a
// terminal answer, on the one surface where her money has already moved.
describe("BookPage pay step", () => {
  /**
   * The VISIBLE occurrences of a string.
   *
   * Every headline on this step is rendered twice by design — once on the page
   * and once inside the one visually-hidden status region that announces it —
   * so a bare getByText matches both. Filtering by `.sr-only` ancestry keeps
   * these assertions about what she SEES, with the announcement asserted
   * separately through role="status".
   */
  function visiblePay(value: string): HTMLElement[] {
    return screen.queryAllByText(value).filter((node) => node.closest(".sr-only") === null);
  }

  async function findVisiblePay(value: string): Promise<HTMLElement> {
    await waitFor(() => {
      expect(visiblePay(value)).toHaveLength(1);
    });
    return visiblePay(value)[0];
  }

  async function bookDeposit(overrides: Partial<BookingCreateResponse> = {}) {
    createBooking.mockResolvedValue(depositBooking(overrides));
    const result = await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());
    // The URL, not a string: with a terminal poll answer already mocked the
    // hand-off copy may never render, and waiting on it would make the state
    // tests below unreachable.
    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/pay");
    });
    return result;
  }

  it("routes a deposit-due booking to the pay step, never to the confirmation", async () => {
    // D11: the booking is written FIRST, as `pending_payment`. Landing her on
    // the confirmation screen would tell her an appointment is confirmed before
    // a single agora is taken — which is also why the router suppresses the SMS.
    await bookDeposit();

    expect(screen.queryByText(i18n.t("booking.confirmKeepScreen"))).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("booking.payTitle"));
    // Not a step of the stepper: the four dots end at verify.
    expect(screen.queryByRole("list", { name: i18n.t("booking.stepsLabel") })).toBeNull();
  });

  it("still ends a no-deposit booking at the confirmation screen", async () => {
    createBooking.mockResolvedValue(booking());
    await walkToVerify();
    await sendCode();
    enterCode();
    fireEvent.click(submitButton());

    expect(await screen.findByText(i18n.t("booking.confirmKeepScreen"))).toBeInTheDocument();
    expect(window.location.pathname).toBe("/book/confirm");
    expect(handOffSpy).not.toHaveBeenCalled();
  });

  // --- state A: the hand-off ----------------------------------------------

  it("hands off to the provider AND leaves a manual link for a browser that blocked it", async () => {
    await bookDeposit();

    await findVisiblePay(i18n.t("booking.payHandoff"));
    expect(handOffSpy).toHaveBeenCalledWith(CHECKOUT);
    // The fallback is not decoration. A blocked automatic redirect leaves this
    // link as the ONLY way to the money, so it ships with the state, not after
    // a timeout that a stalled tab never reaches.
    const link = screen.getByRole("link", { name: i18n.t("booking.payManualCta") });
    expect(link).toHaveAttribute("href", CHECKOUT);
    // rel=external, because the dev gateway's page is SAME-ORIGIN
    // ("/fake-pay?session=…") and the app's delegated click handler would
    // otherwise swallow it into a client navigation that matches no route.
    expect(link).toHaveAttribute("rel", "external");
    expect(screen.getByText(i18n.t("booking.payManualHint"))).toBeInTheDocument();
  });

  it("carries the poll credential in the URL, so a reload does not lose her payment", async () => {
    // Device storage is banned on this surface and the create response lives in
    // memory alone. Without this the whole awaiting state is unreachable after
    // any reload — and a reload is exactly what a hand-off out of the app is.
    await bookDeposit();

    expect(new URLSearchParams(window.location.search).get("session")).toBe(SESSION);
  });

  it("issues the hand-off once, however many times the step re-renders", async () => {
    // The poll re-renders this step on its own clock. Re-issuing the redirect
    // there traps her in a loop between the boutique and the provider — and a
    // back navigation out of the hosted page is the common case, not the rare
    // one.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      await bookDeposit();
      await findVisiblePay(i18n.t("booking.payHandoff"));
      for (let tick = 0; tick < 3; tick += 1) {
        await act(async () => {
          vi.advanceTimersByTime(3_000);
        });
      }
      expect(handOffSpy).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("refuses a checkout URL that is not http(s) or root-relative", async () => {
    // The URL comes back from a third party. React does NOT neutralise a
    // javascript: href, and this one is both navigated to and rendered.
    await bookDeposit({ redirect_url: "javascript:alert(1)" });

    expect(handOffSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole("link", { name: i18n.t("booking.payManualCta") })).toBeNull();
  });

  // --- state B: returned, awaiting the webhook -----------------------------

  it("polls the session on a cold return and says it is confirming, not that it is done", async () => {
    // THE WEBHOOK IS AUTHORITATIVE, NOT THE RETURN REDIRECT. Coming back from
    // the hosted page proves she pressed a button, not that money moved.
    renderFlow(`/book/pay?session=${SESSION}`);

    // Twice by design: the visible line and the visually-hidden status region
    // that announces it. Both, because aria-busy on a plain div is announced by
    // neither VoiceOver nor NVDA.
    await findVisiblePay(i18n.t("booking.payAwaiting"));
    await waitFor(() => {
      expect(paymentStatus).toHaveBeenCalledWith(SESSION);
    });
    // No link to hand off to on this path, and nothing to redirect.
    expect(handOffSpy).not.toHaveBeenCalled();
    expect(screen.queryByText(i18n.t("booking.confirmKeepScreen"))).toBeNull();
    // R30: aria-busy on a plain div is announced by neither VoiceOver nor NVDA.
    expect(screen.getByRole("status")).toHaveTextContent(i18n.t("booking.payAwaiting"));
  });

  it("spends an attempt on a failed read and keeps asking", async () => {
    // A 429, a dropped connection and a session the server has not written yet
    // are all "no answer yet". One of them must not end the poll.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      paymentStatus.mockRejectedValue(THROTTLED);
      renderFlow(`/book/pay?session=${SESSION}`);
      await findVisiblePay(i18n.t("booking.payAwaiting"));

      await act(async () => {
        vi.advanceTimersByTime(6_000);
      });

      expect(paymentStatus.mock.calls.length).toBeGreaterThan(1);
      expect(visiblePay(i18n.t("booking.payAwaiting"))).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  // --- state C: paid -------------------------------------------------------

  it("stops the poll on the confirmed booking and shows the EXISTING confirmation screen", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      paymentStatus.mockResolvedValue(payFacts());
      await bookDeposit();
      await findVisiblePay(i18n.t("booking.payHandoff"));
      paymentStatus.mockResolvedValue(
        payFacts({ booking_status: "confirmed", payment_status: "paid", paid_at: AUG4_1000 }),
      );

      await act(async () => {
        vi.advanceTimersByTime(3_000);
      });

      await waitFor(() => {
        expect(window.location.pathname).toBe("/book/confirm");
      });
      // Unchanged, not redesigned: the same card, the same keep-the-screen line.
      expect(screen.getByText(i18n.t("booking.confirmKeepScreen"))).toBeInTheDocument();
      expect(screen.getByText(i18n.t("booking.confirmWhen"))).toBeInTheDocument();

      // TERMINAL: the interval is gone, not merely ignored.
      const settled = paymentStatus.mock.calls.length;
      await act(async () => {
        vi.advanceTimersByTime(60_000);
      });
      expect(paymentStatus).toHaveBeenCalledTimes(settled);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps asking while the money is in but the booking is not yet confirmed", async () => {
    // D3's crash window: `settle_from_webhook` commits `payments -> paid` in its
    // own transaction and the booking confirm is a SECOND one. Confirming the
    // appointment here would claim something the server has not written; a
    // redelivery is the repair, so the honest move is to keep asking.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      paymentStatus.mockResolvedValue(
        payFacts({ booking_status: "pending_payment", payment_status: "paid", paid_at: AUG4_1000 }),
      );
      renderFlow(`/book/pay?session=${SESSION}`);
      await findVisiblePay(i18n.t("booking.payAwaiting"));

      await act(async () => {
        vi.advanceTimersByTime(6_000);
      });

      expect(window.location.pathname).toBe("/book/pay");
      expect(visiblePay(i18n.t("booking.payAwaiting"))).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  // --- state D: declined ---------------------------------------------------

  it("offers the SAME link on a decline, and promises no fresh attempt or new price", async () => {
    // D11b/D8: a retry converges onto the same hold and returns the same link,
    // so the copy may not imply a second booking or a second amount.
    //
    // The payload is the one the BACKEND actually emits, and the distinction is
    // the whole reason this state was unreachable in review: a declined hold
    // stays `pending` on purpose so the sweeper owns the seat and a retried card
    // settles the same hold. `payment_status: "failed"` is written only by
    // `record_unavailable`, which leaves `provider_session_id` NULL and so can
    // never be found by this poll at all — driving the screen from it pinned a
    // shape no server response can have.
    paymentStatus.mockResolvedValue(payFacts({ declined: true }));
    await bookDeposit();

    await findVisiblePay(i18n.t("booking.payDeclined"));
    expect(screen.getByText(i18n.t("booking.payDeclinedBody"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("booking.payManualCta") })).toHaveAttribute(
      "href",
      CHECKOUT,
    );
    // No sum anywhere in the sentence: naming one here would be the screen
    // inventing a price the hold already fixed.
    expect(i18n.t("booking.payDeclinedBody")).not.toMatch(/\d/);
    expect(visiblePay(i18n.t("booking.payHandoff"))).toHaveLength(0);
    // The POLL made this happen, not a tap: there is no control to move focus
    // from, so the status region is the only thing that tells a screen reader
    // the wait is over. Moving focus instead would be a 3.2.1 defect of its own.
    expect(screen.getByRole("status")).toHaveTextContent(i18n.t("booking.payDeclined"));
  });

  // --- state E: expired ----------------------------------------------------

  it("sends an expired hold back to the ordinary slot picker, with no retry link", async () => {
    // The seat is gone: the sweeper cancelled the booking and freed it. Offering
    // the old checkout link would take her money for a time she no longer has.
    paymentStatus.mockResolvedValue(
      payFacts({ booking_status: "cancelled", payment_status: "expired" }),
    );
    await bookDeposit();

    await findVisiblePay(i18n.t("booking.payExpired"));
    expect(screen.getByRole("link", { name: i18n.t("manage.rebookCta") })).toHaveAttribute(
      "href",
      "/book/slot",
    );
    expect(screen.queryByRole("link", { name: i18n.t("booking.payManualCta") })).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent(i18n.t("booking.payExpired"));
  });

  it("actually lets her rebook after an expiry, instead of forwarding her to a dead booking", async () => {
    // The guard forwards `verify` to /book/confirm while a booking is in
    // memory. That is right while the booking is alive and wrong the moment the
    // sweeper cancelled it — without the clear, this link walks her three steps
    // forward into the appointment she just lost and offers no fourth.
    paymentStatus.mockResolvedValue(
      payFacts({ booking_status: "cancelled", payment_status: "expired" }),
    );
    await bookDeposit();
    await findVisiblePay(i18n.t("booking.payExpired"));

    fireEvent.click(screen.getByRole("link", { name: i18n.t("manage.rebookCta") }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/book/slot");
    });
    // A real slot picker, walked forward — not a bounce back to the dead one.
    await pickFirstType();
    fireEvent.click(await screen.findByRole("radio", { name: "10:00" }));
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/details");
    expect(visiblePay(i18n.t("booking.payExpired"))).toHaveLength(0);
  });

  // --- the state that gets forgotten: bounded attempts, no terminal answer --

  it("stops after the bounded attempts and hands her the phone, never a spinner forever", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      paymentStatus.mockResolvedValue(payFacts());
      renderFlow(`/book/pay?session=${SESSION}`);
      await findVisiblePay(i18n.t("booking.payAwaiting"));

      // 20 attempts at 3s. The first fires on mount, so 19 ticks exhaust it.
      for (let tick = 0; tick < 19; tick += 1) {
        await act(async () => {
          vi.advanceTimersByTime(3_000);
        });
      }

      await findVisiblePay(i18n.t("booking.payUnresolved"));
      // Exactly the bound, so this cannot pass by reaching the state some other
      // way — a missing session id renders the same copy, and that is the one
      // thing this test must not be measuring.
      expect(paymentStatus).toHaveBeenCalledTimes(20);
      // It really stopped — an unbounded poll on a money screen is a battery
      // drain and a request storm, and it never reaches an answer either.
      const settled = paymentStatus.mock.calls.length;
      await act(async () => {
        vi.advanceTimersByTime(60_000);
      });
      expect(paymentStatus).toHaveBeenCalledTimes(settled);
      // The phone, because this is the one state the product cannot resolve.
      expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
      // It may NOT say the payment failed: her card may well have been charged.
      expect(visiblePay(i18n.t("booking.payDeclined"))).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("says the same thing on a pay URL with no session at all, and does not bounce her", async () => {
    // A hand-typed URL, or a return that lost the query. The booking may exist
    // and the money may have moved, so walking her back to step one would invite
    // a second appointment and a second deposit.
    renderFlow("/book/pay");

    await findVisiblePay(i18n.t("booking.payUnresolved"));
    expect(window.location.pathname).toBe("/book/pay");
    expect(paymentStatus).not.toHaveBeenCalled();
  });

  it("never prints a raw status value onto a Hebrew screen", async () => {
    paymentStatus.mockResolvedValue(payFacts({ declined: true }));
    await bookDeposit();

    await findVisiblePay(i18n.t("booking.payDeclined"));
    expect(screen.queryByText(/pending_payment|failed|expired/)).toBeNull();
  });
});
