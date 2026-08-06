// F22's inline reveal on the slot step (design §1-3). State assertions only —
// the focus-movement rules (§7) are Playwright's, measured in a real browser
// (waitlist.spec.ts); jsdom focus is asserted nowhere here on purpose.
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { BookPage } from "../routes/BookPage";
import { PRIVACY_FIXTURE } from "../test/boutique";
import type { AppointmentTypeRow, BoutiqueResponse } from "../api";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTerms: vi.fn(),
      listAppointmentTypes: vi.fn(),
      listSlots: vi.fn(),
      sendOtp: vi.fn(),
      verifyOtp: vi.fn(),
      joinWaitlist: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const getTerms = vi.mocked(api.getTerms);
const listTypes = vi.mocked(api.listAppointmentTypes);
const listSlots = vi.mocked(api.listSlots);
const sendOtp = vi.mocked(api.sendOtp);
const verifyOtp = vi.mocked(api.verifyOtp);
const joinWaitlist = vi.mocked(api.joinWaitlist);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const OTP_WRONG = new ApiError(400, "OTP_INVALID", "Invalid code.");
const THROTTLED = new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts.");

// One slot on Aug 4 only, so picking Aug 5 renders the full-day empty state
// with a real picked date for the entry to bind to.
const AUG4_1000 = "2026-08-04T07:00:00Z";
const EMPTY_DAY = "2026-08-05";

const TYPED_PHONE = "050-123 4567";
const WIRE_PHONE = "+972501234567";

function boutique(): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: "052-1234567",
    address: null,
    maps_url: null,
    instagram: null,
    hours: [],
    exceptions: [],
    ...PRIVACY_FIXTURE,
  };
}

function appointmentType(): AppointmentTypeRow {
  return {
    id: "t1",
    name: "מדידה ראשונה",
    duration_minutes: 45,
    audience: "all",
    deposit_required: false,
    deposit_amount_agorot: null,
  };
}

function renderSlotStep() {
  return render(
    <StorefrontLayout>
      <BookPage step="slot" />
    </StorefrontLayout>,
  );
}

function cta() {
  return screen.queryByRole("button", { name: i18n.t("waitlist.cta") });
}

async function pickType() {
  fireEvent.click(await screen.findByRole("radio", { name: /מדידה ראשונה/ }));
}

function pickEmptyDay() {
  fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
    target: { value: EMPTY_DAY },
  });
}

async function openReveal() {
  renderSlotStep();
  await pickType();
  pickEmptyDay();
  fireEvent.click(cta()!);
}

function sendButton() {
  return screen.getByRole("button", { name: i18n.t("waitlist.send") });
}

async function sendCode() {
  fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
    target: { value: TYPED_PHONE },
  });
  fireEvent.click(sendButton());
  return screen.findByLabelText(i18n.t("booking.otpCode"));
}

async function join(code = "123456") {
  fireEvent.change(await screen.findByLabelText(i18n.t("booking.otpCode")), {
    target: { value: code },
  });
  fireEvent.click(screen.getByRole("button", { name: i18n.t("waitlist.join") }));
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  getTerms.mockResolvedValue({
    version: 1,
    terms_text: "תנאים",
    refundable_until_hours_before: 48,
    forfeit_percent: 50,
  });
  listTypes.mockResolvedValue([appointmentType()]);
  listSlots.mockResolvedValue({ slots: [{ starts_at: AUG4_1000 }] });
  sendOtp.mockResolvedValue(undefined);
  verifyOtp.mockResolvedValue({
    verification_token: "vt-1",
    expires_at: "2026-08-05T07:10:00Z",
  });
  joinWaitlist.mockResolvedValue({
    day: EMPTY_DAY,
    appointment_type_id: "t1",
    status: "waiting",
  });
  window.history.replaceState(null, "", "/book/slot");
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("the CTA's gate", () => {
  it("is absent while the picked day has times", async () => {
    renderSlotStep();
    await pickType();
    expect(await screen.findByRole("radio", { name: "10:00" })).toBeInTheDocument();
    expect(cta()).toBeNull();
  });

  it("is absent on an empty day until a type is picked — it must not invite a join it cannot bind", async () => {
    renderSlotStep();
    await screen.findByRole("radio", { name: /מדידה ראשונה/ });
    pickEmptyDay();
    expect(screen.getByText(i18n.t("booking.noSlots"))).toBeInTheDocument();
    expect(cta()).toBeNull();
    await pickType();
    expect(cta()).not.toBeNull();
  });
});

describe("the reveal", () => {
  it("opens with the phone phase and the privacy notice ABOVE the send control", async () => {
    await openReveal();
    expect(screen.getByLabelText(i18n.t("booking.phone"))).toBeInTheDocument();
    // The shipped notice verbatim, boutique name substituted — D4's whole Gate 1
    // argument. PRIVACY_FIXTURE carries {{boutique}}, so finding the substituted
    // name proves substituteBoutique ran.
    expect(screen.getByTestId("waitlist-privacy-notice").textContent).toContain("בוטיק אלמה");
    // No code field before a send.
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
  });

  it("refuses a malformed phone client-side and sends nothing", async () => {
    await openReveal();
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: "123" },
    });
    fireEvent.click(sendButton());
    expect(await screen.findByText(i18n.t("booking.phoneInvalid"))).toBeInTheDocument();
    expect(sendOtp).not.toHaveBeenCalled();
  });

  it("sends the normalised phone, mounts the code phase and cools the send control", async () => {
    await openReveal();
    await sendCode();
    expect(sendOtp).toHaveBeenCalledWith(WIRE_PHONE);
    // One label for send and resend, and while cooling the label IS the
    // explanation — disabled drops it from the tab order.
    const cooling = screen.getByRole("button", { name: i18n.t("waitlist.sendWait") });
    expect(cooling).toBeDisabled();
    expect(screen.getByRole("button", { name: i18n.t("waitlist.join") })).toBeInTheDocument();
  });

  it("joins with EXACTLY the four wire keys", async () => {
    await openReveal();
    await sendCode();
    await join();
    await screen.findByTestId("waitlist-confirmed");
    expect(verifyOtp).toHaveBeenCalledWith(WIRE_PHONE, "123456");
    expect(joinWaitlist).toHaveBeenCalledTimes(1);
    const body = joinWaitlist.mock.calls[0][0];
    // Key-set EQUALITY, not containment: a fifth field (name, consent, dress)
    // riding in is the failure this pins.
    expect(Object.keys(body).sort()).toEqual([
      "appointment_type_id",
      "day",
      "phone",
      "verification_token",
    ]);
    expect(body).toEqual({
      phone: WIRE_PHONE,
      verification_token: "vt-1",
      day: EMPTY_DAY,
      appointment_type_id: "t1",
    });
  });

  it("replaces the whole reveal with the confirmation line on 201", async () => {
    await openReveal();
    await sendCode();
    await join();
    const confirmation = await screen.findByTestId("waitlist-confirmed");
    expect(confirmation).toHaveAttribute("role", "status");
    expect(confirmation.textContent).toContain("נרשמת לרשימת ההמתנה");
    // No exclamation mark — the register rule.
    expect(confirmation.textContent).not.toContain("!");
    // The form is gone, both phases of it.
    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
  });

  it("maps a wrong code onto the code field and a join 429 onto the step line", async () => {
    verifyOtp.mockRejectedValueOnce(OTP_WRONG);
    await openReveal();
    await sendCode();
    await join();
    expect(await screen.findByText(i18n.t("errors.otpInvalid"))).toBeInTheDocument();
    expect(joinWaitlist).not.toHaveBeenCalled();

    joinWaitlist.mockRejectedValueOnce(THROTTLED);
    await join();
    expect(await screen.findByText(i18n.t("errors.tooManyAttempts"))).toBeInTheDocument();
    expect(screen.queryByTestId("waitlist-confirmed")).toBeNull();
  });

  it("F-W3: a date change collapses the reveal AND clears the code/token state", async () => {
    await openReveal();
    await sendCode();
    // A verified-but-unjoined token in hand — the exact state F-W3 warns about.
    joinWaitlist.mockRejectedValueOnce(THROTTLED);
    await join();
    await screen.findByText(i18n.t("errors.tooManyAttempts"));
    expect(verifyOtp).toHaveBeenCalledTimes(1);
    // Collapse: the day the reveal bound to is gone.
    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-06" },
    });
    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    // Re-open: phone phase again — no surviving code field, so no stale token
    // for the old day can ride into the new reveal.
    fireEvent.click(cta()!);
    expect(screen.getByLabelText(i18n.t("booking.phone"))).toBeInTheDocument();
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
    // The fresh join RE-VERIFIES — a held token surviving the collapse would
    // have skipped this second verify and joined the new day on the old proof.
    await sendCode();
    await join();
    await screen.findByTestId("waitlist-confirmed");
    expect(verifyOtp).toHaveBeenCalledTimes(2);
  });

  it("a type change collapses the reveal too", async () => {
    listTypes.mockResolvedValue([
      appointmentType(),
      { ...appointmentType(), id: "t2", name: "מדידה שנייה" },
    ]);
    await openReveal();
    await sendCode();
    fireEvent.click(screen.getByRole("radio", { name: /מדידה שנייה/ }));
    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    expect(cta()).not.toBeNull();
  });
});

describe("the i18n contract", () => {
  it("ships the seven waitlist keys in he and mirrors them in ar", async () => {
    const { he } = await import("../i18n/he");
    const { ar } = await import("../i18n/ar");
    const heBlock = (he.translation as Record<string, unknown>).waitlist as Record<string, string>;
    const arBlock = (ar.translation as Record<string, unknown>).waitlist as Record<string, string>;
    expect(Object.keys(heBlock).length).toBeGreaterThanOrEqual(7);
    for (const [key, value] of Object.entries(heBlock)) {
      expect(arBlock[key], `ar.ts is missing waitlist.${key}`).toBe(value);
      expect(value).not.toContain("!");
    }
  });
});
