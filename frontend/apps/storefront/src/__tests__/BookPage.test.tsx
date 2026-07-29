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
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { SizeChips } from "../components/booking/SizeChips";
import { SlotPicker } from "../components/booking/SlotPicker";
import { TypePicker } from "../components/booking/TypePicker";
import { BookPage } from "../routes/BookPage";
import { matchRoute, usePathname } from "../router";

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
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
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
    expect(document.activeElement).toBe(code);
    // R16: otpSent is the field's help text, spoken once by aria-describedby as
    // focus arrives. A live region here would double-announce it.
    expect(code).toHaveAccessibleDescription(new RegExp(i18n.t("booking.otpSent")));
    expect(screen.queryByText(i18n.t("booking.otpSent"))).not.toHaveAttribute("role", "status");
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

      act(() => {
        vi.advanceTimersByTime(60_000);
      });

      expect(resend()).toBeEnabled();
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
    expect(document.activeElement).toBe(block.closest("[tabindex]"));
    // The h1 and the way back both stay: she is not trapped.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("booking.stepOtp"));
    expect(screen.getByRole("link", { name: i18n.t("booking.backStep") })).toBeInTheDocument();
  });

  it.each(["SMS_NOT_CONFIGURED", "SMS_UNAVAILABLE"])(
    "replaces the form with the phone-only exit on %s",
    async (code) => {
      sendOtp.mockRejectedValue(new ApiError(503, code, "sms down"));

      await walkToVerify();
      fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
        target: { value: TYPED_PHONE },
      });
      fireEvent.click(resend());

      // To the visitor "misconfigured" and "provider down" are the same dead end.
      expect(await screen.findByText(i18n.t("errors.smsUnavailable"))).toBeInTheDocument();
      expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
      expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    },
  );

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
    expect(document.activeElement).toBe(code);
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
    await waitFor(() => {
      expect(document.activeElement).toBe(phone);
    });

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

  it.each([
    ["a 500", BROKEN],
    ["a spent create budget", THROTTLED],
  ])("keeps R13 as the final fallback for %s on submit", async (_label, error) => {
    await readyToSubmit();
    createBooking.mockRejectedValueOnce(error);

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
