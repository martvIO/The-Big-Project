// F24's /portal route: the login chain, the dashboard, the badge policy and the
// bell's seen contract. State assertions only — the focus-movement rules
// (design §10) are Playwright's, measured in a real browser (portal.spec.ts),
// because jsdom's focus model is not the one a screen reader follows.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { PortalPage } from "../routes/PortalPage";
import { PRIVACY_FIXTURE } from "../test/boutique";
import type { BoutiqueResponse, ManageBookingResponse, PortalBookings } from "../api";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      sendOtp: vi.fn(),
      verifyOtp: vi.fn(),
      portalMe: vi.fn(),
      portalLogin: vi.fn(),
      portalLogout: vi.fn(),
      portalBookings: vi.fn(),
      portalBooking: vi.fn(),
      portalConfirmAttendance: vi.fn(),
      portalCancel: vi.fn(),
      portalBell: vi.fn(),
      portalBellSeen: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const sendOtp = vi.mocked(api.sendOtp);
const verifyOtp = vi.mocked(api.verifyOtp);
const portalMe = vi.mocked(api.portalMe);
const portalLogin = vi.mocked(api.portalLogin);
const portalLogout = vi.mocked(api.portalLogout);
const portalBookings = vi.mocked(api.portalBookings);
const portalBooking = vi.mocked(api.portalBooking);
const portalCancel = vi.mocked(api.portalCancel);
const portalBell = vi.mocked(api.portalBell);
const portalBellSeen = vi.mocked(api.portalBellSeen);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const UNAUTHENTICATED = new ApiError(401, "NOT_AUTHENTICATED", "Authentication required.");
const NO_BOOKINGS = new ApiError(404, "PORTAL_NO_BOOKINGS", "No bookings.");
const PHONE_NOT_VERIFIED = new ApiError(403, "PHONE_NOT_VERIFIED", "Not verified.");
const THROTTLED = new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts.");

const TYPED_PHONE = "050-123 4567";
const WIRE_PHONE = "+972501234567";
const BOOKING_ID = "11111111-1111-1111-1111-111111111111";

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

function bookings(overrides: Partial<PortalBookings> = {}): PortalBookings {
  return {
    upcoming: [
      {
        id: BOOKING_ID,
        starts_at: "2099-08-04T07:00:00Z",
        status: "confirmed",
        attendance_confirmed_at: null,
        appointment_type_name: "מדידה ראשונה",
        dress_name: "שמלת אלמה",
        dress_size: "36",
      },
    ],
    past: [],
    ...overrides,
  };
}

function detail(status = "confirmed"): ManageBookingResponse {
  return {
    booking: {
      starts_at: "2099-08-04T07:00:00Z",
      status,
      attendance_confirmed_at: null,
      appointment_type_name: "מדידה ראשונה",
      dress_name: "שמלת אלמה",
      dress_size: "36",
      deposit_taken: false,
    },
    policy: { refundable_until_hours_before: 48, forfeit_percent: 50 },
    boutique: { name: "בוטיק אלמה", phone: "052-1234567", address: null, maps_url: null },
  };
}

function renderPortal() {
  return render(
    <StorefrontLayout>
      <PortalPage />
    </StorefrontLayout>,
  );
}

async function signIn() {
  portalMe.mockResolvedValue({ customer_name: "רותם" });
  renderPortal();
  await screen.findByText(/רותם/);
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  portalBookings.mockResolvedValue(bookings());
  portalBell.mockResolvedValue({ unread_count: 0, items: [] });
  portalBellSeen.mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// --- the bootstrap ----------------------------------------------------------

describe("the /portal bootstrap", () => {
  it("renders the login panel when the session probe 401s", async () => {
    portalMe.mockRejectedValue(UNAUTHENTICATED);
    renderPortal();
    expect(await screen.findByText(i18n.t("portal.loginIntro"))).toBeInTheDocument();
    // A 401 is a STATE and never an error — no failure copy anywhere.
    expect(screen.queryByText(i18n.t("manage.loadFailed"))).toBeNull();
  });

  it("renders the dashboard when the session probe answers", async () => {
    await signIn();
    expect(await screen.findByText(i18n.t("portal.upcoming"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("portal.loginIntro"))).toBeNull();
  });
});

// --- the login chain --------------------------------------------------------

describe("the login panel", () => {
  beforeEach(() => {
    portalMe.mockRejectedValue(UNAUTHENTICATED);
  });

  async function fillPhoneAndSend() {
    renderPortal();
    const phone = await screen.findByLabelText(i18n.t("booking.phone"));
    fireEvent.change(phone, { target: { value: TYPED_PHONE } });
    sendOtp.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.otpResend") }));
    return await screen.findByLabelText(i18n.t("booking.otpCode"));
  }

  it("chains verify then mint on ONE click of כניסה (design P1)", async () => {
    const code = await fillPhoneAndSend();
    fireEvent.change(code, { target: { value: "123456" } });
    verifyOtp.mockResolvedValue({ verification_token: "vt-1", expires_at: "2099-01-01T00:00:00Z" });
    portalLogin.mockResolvedValue({ customer_name: "רותם" });

    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.loginSubmit") }));

    await waitFor(() => {
      expect(portalLogin).toHaveBeenCalledWith({
        phone: WIRE_PHONE,
        verification_token: "vt-1",
      });
    });
    expect(verifyOtp).toHaveBeenCalledTimes(1);
  });

  it("E7: a 429 on the MINT re-fires the mint alone, never a second verify", async () => {
    const code = await fillPhoneAndSend();
    fireEvent.change(code, { target: { value: "123456" } });
    verifyOtp.mockResolvedValue({ verification_token: "vt-1", expires_at: "2099-01-01T00:00:00Z" });
    portalLogin.mockRejectedValueOnce(THROTTLED);

    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.loginSubmit") }));
    expect(await screen.findByText(i18n.t("errors.tooManyAttempts"))).toBeInTheDocument();
    // The form stays intact: the brake is the tenant's, not her typing.
    expect(screen.getByLabelText(i18n.t("booking.otpCode"))).toBeInTheDocument();

    portalLogin.mockResolvedValue({ customer_name: "רותם" });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.loginSubmit") }));
    await waitFor(() => {
      expect(portalLogin).toHaveBeenCalledTimes(2);
    });
    // The held token was never spent, so the code was never re-verified.
    expect(verifyOtp).toHaveBeenCalledTimes(1);
  });

  it("F-P1: PHONE_NOT_VERIFIED renders portal.verifyExpired, not errors.phoneNotVerified", async () => {
    const code = await fillPhoneAndSend();
    fireEvent.change(code, { target: { value: "123456" } });
    verifyOtp.mockResolvedValue({ verification_token: "vt-1", expires_at: "2099-01-01T00:00:00Z" });
    portalLogin.mockRejectedValue(PHONE_NOT_VERIFIED);

    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.loginSubmit") }));

    expect(await screen.findByText(i18n.t("portal.verifyExpired"))).toBeInTheDocument();
    // The booking-flow row's tail ("הפרטים שמילאת נשמרו") promises a saved form
    // this surface does not have.
    expect(screen.queryByText(i18n.t("errors.phoneNotVerified"))).toBeNull();
  });

  it("state N renders the SAME screen as the empty dashboard (design P2)", async () => {
    const code = await fillPhoneAndSend();
    fireEvent.change(code, { target: { value: "123456" } });
    verifyOtp.mockResolvedValue({ verification_token: "vt-1", expires_at: "2099-01-01T00:00:00Z" });
    portalLogin.mockRejectedValue(NO_BOOKINGS);

    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.loginSubmit") }));

    expect(await screen.findByText(i18n.t("portal.emptyTitle"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("portal.emptyBody"))).toBeInTheDocument();
    expect(screen.getByTestId("portal-empty")).toBeInTheDocument();
  });

  it("editing the phone collapses the code field and drops the held token", async () => {
    const code = await fillPhoneAndSend();
    fireEvent.change(code, { target: { value: "123456" } });
    fireEvent.change(screen.getByLabelText(i18n.t("booking.phone")), {
      target: { value: "0529999999" },
    });
    expect(screen.queryByLabelText(i18n.t("booking.otpCode"))).toBeNull();
  });

  it("E6: an SMS outage replaces the form with a dead end and the phone", async () => {
    renderPortal();
    const phone = await screen.findByLabelText(i18n.t("booking.phone"));
    fireEvent.change(phone, { target: { value: TYPED_PHONE } });
    sendOtp.mockRejectedValue(new ApiError(503, "SMS_UNAVAILABLE", "down"));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.otpResend") }));

    expect(await screen.findByText(i18n.t("errors.smsUnavailable"))).toBeInTheDocument();
    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
  });
});

// --- the dashboard ----------------------------------------------------------

describe("the bookings dashboard", () => {
  it("renders the empty screen when both sections are empty", async () => {
    portalBookings.mockResolvedValue({ upcoming: [], past: [] });
    await signIn();
    expect(await screen.findByTestId("portal-empty")).toBeInTheDocument();
  });

  it("shows a section-empty line only when the OTHER section has rows", async () => {
    await signIn();
    expect(await screen.findByText(i18n.t("portal.pastEmpty"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("portal.upcomingEmpty"))).toBeNull();
  });

  it("P3: a confirmed row carries NO badge — the default state needs no label", async () => {
    portalBookings.mockResolvedValue(bookings());
    await signIn();
    await screen.findByText(i18n.t("portal.upcoming"));
    expect(screen.queryByText(i18n.t("portal.statusAwaitingPayment"))).toBeNull();
    expect(screen.queryByText(i18n.t("portal.statusCancelled"))).toBeNull();
  });

  it("P3: pending_payment and cancelled DO carry a badge", async () => {
    portalBookings.mockResolvedValue({
      upcoming: [{ ...bookings().upcoming[0], status: "pending_payment" }],
      past: [{ ...bookings().upcoming[0], id: "c", status: "cancelled" }],
    });
    await signIn();
    expect(
      await screen.findByText(i18n.t("portal.statusAwaitingPayment")),
    ).toBeInTheDocument();
    expect(screen.getByText(i18n.t("portal.statusCancelled"))).toBeInTheDocument();
  });

  it("P3: no_show and completed rows carry no badge", async () => {
    portalBookings.mockResolvedValue({
      upcoming: [],
      past: [
        { ...bookings().upcoming[0], id: "a", status: "no_show" },
        { ...bookings().upcoming[0], id: "b", status: "completed" },
      ],
    });
    await signIn();
    await screen.findByText(i18n.t("portal.past"));
    // The boutique's attendance bookkeeping is not rendered back at her.
    expect(screen.queryByText(i18n.t("portal.statusCancelled"))).toBeNull();
    expect(screen.queryByText(i18n.t("portal.statusAwaitingPayment"))).toBeNull();
  });

  it("a failed list offers manage.retry rather than an empty screen", async () => {
    portalBookings.mockRejectedValue(new ApiError(500, "UNKNOWN", "boom"));
    await signIn();
    expect(await screen.findByText(i18n.t("manage.loadFailed"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: i18n.t("manage.retry") })).toBeInTheDocument();
    expect(screen.queryByTestId("portal-empty")).toBeNull();
  });

  it("a mid-session 401 remounts the login panel with the expiry line", async () => {
    portalBookings.mockRejectedValue(UNAUTHENTICATED);
    await signIn();
    // Twice, and both are wanted: the muted line above the card is what she
    // READS, and the status region is what a screen reader HEARS.
    expect(await screen.findAllByText(i18n.t("portal.sessionExpired"))).toHaveLength(2);
    expect(screen.getByText(i18n.t("portal.loginIntro"))).toBeInTheDocument();
  });

  it("logout returns to the login panel with no expiry line", async () => {
    portalLogout.mockResolvedValue({ ok: true });
    await signIn();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.logout") }));
    expect(await screen.findByText(i18n.t("portal.loginIntro"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("portal.sessionExpired"))).toBeNull();
  });
});

// --- the detail -------------------------------------------------------------

describe("the booking detail", () => {
  it("opens from a row and offers the calendar download on a live booking", async () => {
    portalBooking.mockResolvedValue(detail());
    await signIn();
    fireEvent.click(await screen.findByText(/מדידה ראשונה/));
    expect(await screen.findByText(i18n.t("portal.icsDownload"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("portal.backToList"))).toBeInTheDocument();
  });

  it("renders NO calendar control on a cancelled booking", async () => {
    portalBooking.mockResolvedValue(detail("cancelled"));
    await signIn();
    fireEvent.click(await screen.findByText(/מדידה ראשונה/));
    expect(await screen.findByText(i18n.t("manage.cancelled"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("portal.icsDownload"))).toBeNull();
  });

  it("renders NO calendar control and no actions on an unpaid hold", async () => {
    portalBooking.mockResolvedValue(detail("pending_payment"));
    await signIn();
    fireEvent.click(await screen.findByText(/מדידה ראשונה/));
    expect(await screen.findByText(i18n.t("manage.awaitingPayment"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("portal.icsDownload"))).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("manage.cancelCta") })).toBeNull();
  });

  it("a 409 re-renders from the RESPONSE, never from what the tap hoped for", async () => {
    portalBooking.mockResolvedValueOnce(detail()).mockResolvedValue(detail("cancelled"));
    portalCancel.mockRejectedValue(new ApiError(409, "BOOKING_CANCELLED", "already cancelled"));
    await signIn();
    fireEvent.click(await screen.findByText(/מדידה ראשונה/));

    fireEvent.click(await screen.findByRole("button", { name: i18n.t("manage.cancelCta") }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("manage.cancelConfirm") }));

    expect(await screen.findByText(i18n.t("manage.cancelled"))).toBeInTheDocument();
  });

  it("an id that is not hers renders the house 404 with no facts", async () => {
    portalBooking.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    await signIn();
    fireEvent.click(await screen.findByText(/מדידה ראשונה/));
    expect(await screen.findByText(i18n.t("errors.notFound"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("booking.confirmWhen"))).toBeNull();
  });
});

// --- the bell ---------------------------------------------------------------

describe("the bell", () => {
  function bellData(unread = 3) {
    return {
      unread_count: unread,
      items: [
        {
          id: "m1",
          kind: "reminder",
          created_at: "2099-08-01T07:00:00Z",
          booking_id: BOOKING_ID,
          starts_at: "2099-08-04T07:00:00Z",
          appointment_type_name: "מדידה ראשונה",
        },
      ],
    };
  }

  it("F-P2: the badge clears only AFTER the seen POST resolves", async () => {
    let resolveSeen: (value: { ok: boolean }) => void = () => undefined;
    portalBellSeen.mockReturnValue(
      new Promise<{ ok: boolean }>((resolve) => {
        resolveSeen = resolve;
      }),
    );
    portalBell.mockResolvedValue(bellData());
    await signIn();

    const bellButton = await screen.findByRole("button", {
      name: i18n.t("portal.bellLabelUnread", { count: 3 }),
    });
    fireEvent.click(bellButton);
    // Clicked, panel open, POST in flight — the badge is still there, because
    // the SERVER's stamp is the truth and not the click.
    expect(await screen.findByText(i18n.t("portal.bellTitle"))).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: i18n.t("portal.bellLabelUnread", { count: 3 }) }),
    ).toBeInTheDocument();

    resolveSeen({ ok: true });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: i18n.t("portal.bellLabel") })).toBeInTheDocument();
    });
  });

  it("a failed fetch shows NO badge, fires no seen POST, and offers a retry", async () => {
    portalBell.mockRejectedValue(new ApiError(500, "UNKNOWN", "boom"));
    await signIn();
    const bellButton = await screen.findByRole("button", { name: i18n.t("portal.bellLabel") });
    fireEvent.click(bellButton);

    expect(await screen.findByText(i18n.t("portal.bellTitle"))).toBeInTheDocument();
    expect(screen.getAllByText(i18n.t("manage.loadFailed")).length).toBeGreaterThan(0);
    // Nothing was shown, so nothing is marked seen.
    expect(portalBellSeen).not.toHaveBeenCalled();
  });

  it("renders the empty state when the boutique has told her nothing", async () => {
    portalBell.mockResolvedValue({ unread_count: 0, items: [] });
    await signIn();
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("portal.bellLabel") }));
    expect(await screen.findByText(i18n.t("portal.bellEmpty"))).toBeInTheDocument();
  });

  it("skips an unknown kind entirely — a raw enum never reaches the screen", async () => {
    portalBell.mockResolvedValue({
      unread_count: 1,
      items: [{ ...bellData().items[0], kind: "waitlist_offer" }],
    });
    await signIn();
    fireEvent.click(
      await screen.findByRole("button", {
        name: i18n.t("portal.bellLabelUnread", { count: 1 }),
      }),
    );
    expect(await screen.findByText(i18n.t("portal.bellEmpty"))).toBeInTheDocument();
    expect(screen.queryByText(/waitlist_offer/)).toBeNull();
  });

  it("caps the visible badge at 9+ while the accessible name carries the count", async () => {
    portalBell.mockResolvedValue(bellData(23));
    await signIn();
    const bellButton = await screen.findByRole("button", {
      name: i18n.t("portal.bellLabelUnread", { count: 23 }),
    });
    expect(bellButton.textContent).toContain("9+");
    expect(bellButton.textContent).not.toContain("23");
  });
});
