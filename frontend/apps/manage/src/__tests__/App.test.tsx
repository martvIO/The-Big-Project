import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { SosAlert, Staff } from "../api";
import { App } from "../App";

/**
 * The four lines that make the emergency channel exist at all — and one of them
 * is the only thing in this console that can drop it to the login form.
 *
 * ⚠ A NEW FILE RATHER THAN A BLOCK IN `Nav.test.tsx`, and that is an assertion
 * rather than a preference: `Nav.test.tsx` must have an EMPTY diff on this PR,
 * because its three role counts and its `NAV_LABELS` length are what prove F37
 * added no fourteenth section and no nav row. An alert is an interruption, not a
 * destination.
 */

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  const pending = () => new Promise(() => {});
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    FALLBACK_ERROR_MESSAGE: actual.FALLBACK_ERROR_MESSAGE,
    api: {
      me: vi.fn(),
      login: vi.fn(),
      logout: vi.fn().mockResolvedValue({ ok: true }),
      getDashboard: pending,
      getSettings: pending,
      getAvailability: pending,
      listAppointmentTypes: pending,
      getTerms: pending,
      listDresses: pending,
      listBookings: pending,
      listCustomers: pending,
      listStaff: pending,
      getSos: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const me = vi.mocked(api.me);
const getSos = vi.mocked(api.getSos);

const NOW = "2026-08-04T08:25:00Z";
const ALERT_A = "aaaaaaaa-0000-0000-0000-00000000000a";

const STAFF: Staff = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "sara@bella.example",
  display_name: "שרה",
  role: "owner",
};

function alertRow(): SosAlert {
  return {
    id: ALERT_A,
    status: "open",
    raised_by: "22222222-2222-2222-2222-222222222222",
    raised_by_name: "דנה כהן",
    target_staff_user_id: null,
    target_name: null,
    room_label: "חדר 2",
    note: "צריך סיכות",
    accepted_by: null,
    accepted_by_name: null,
    acknowledged_at: null,
    created_at: "2026-08-04T08:20:00Z",
    escalated: false,
    stalled: false,
    for_me: true,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.clearAllMocks();
  me.mockResolvedValue(STAFF);
  getSos.mockResolvedValue({ alerts: [], server_now: NOW });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the overlay is mounted app-level, before the shell", () => {
  it("puts the rising card BEFORE #console-main in DOM order", async () => {
    // So its controls precede every other focusable in the document — which is
    // what makes «first in DOM is first reached by Tab» true once focus is in
    // the overlay, and what the Esc route-in exists to reach when it is not.
    getSos.mockResolvedValue({ alerts: [alertRow()], server_now: NOW });
    render(<App />);
    await screen.findByText("דנה כהן");

    const card = document.querySelector(`[data-alert-id="${ALERT_A}"]`);
    const main = document.getElementById("console-main");
    expect(card).not.toBeNull();
    expect(main).not.toBeNull();
    // DOCUMENT_POSITION_FOLLOWING === 4: `main` comes after `card`.
    expect((card as Element).compareDocumentPosition(main as Element) & 4).toBe(
      4,
    );
  });

  it("renders NOTHING extra on a console with no alert — the normal state costs no DOM", async () => {
    render(<App />);
    await screen.findByRole("navigation");

    expect(document.querySelector("[data-alert-id]")).toBeNull();
    expect(document.querySelector(".bg-danger")).toBeNull();
  });
});

describe("AC27 — a 401 on an SOS tick drops the console to the login form", () => {
  it("fires the provider's onSessionEnded, which is the setStaff(null) App already had", async () => {
    // ⚠ The spec's earlier claim that «App will show the login form on her next
    // navigation» is FALSE against shipped code: `staff` is cleared in exactly
    // two places — the initial `api.me().catch()` and `handleLogout` — there is
    // no fetch interceptor, and `onNavigate` is just `setSection`. Without this
    // callback the console keeps rendering a working-looking shell over a dead
    // emergency channel, on eleven sections that poll nothing else.
    getSos.mockRejectedValue(new ApiError(401, "UNAUTHENTICATED", "gone"));
    render(<App />);
    await screen.findByRole("navigation");

    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => expect(screen.queryByRole("navigation")).toBeNull());
    expect(screen.getByRole("textbox", { name: "אימייל" })).toBeInTheDocument();
  });
});
