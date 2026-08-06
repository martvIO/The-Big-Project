// F22's console section (design §4). State assertions only — focus movement
// after a row removal is Playwright's (waitlist.spec.ts).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../i18n";
import type { BookingWaitlistRow } from "../api";
import { WaitlistSection } from "../components/WaitlistSection";
import { todayJerusalem } from "../lib/jerusalem";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getBookingWaitlist: vi.fn(),
      cancelBookingWaitlistEntry: vi.fn(),
    },
  };
});

const { api } = await import("../api");
const getList = vi.mocked(api.getBookingWaitlist);
const cancelEntry = vi.mocked(api.cancelBookingWaitlistEntry);

function row(overrides: Partial<BookingWaitlistRow> = {}): BookingWaitlistRow {
  return {
    id: "we-1",
    day: "2026-08-20",
    appointment_type_id: "apt-1",
    appointment_type_name: "מדידה ראשונה",
    phone: "+972501234567",
    customer_name: "נועה לוי",
    status: "waiting",
    created_at: "2026-08-01T06:30:00Z",
    ...overrides,
  };
}

const STRANGER = row({
  id: "we-2",
  customer_name: null,
  phone: "+972529998877",
  created_at: "2026-08-01T07:00:00Z",
});

beforeEach(() => {
  vi.clearAllMocks();
  getList.mockResolvedValue({ entries: [row(), STRANGER] });
  cancelEntry.mockResolvedValue({ ...row(), status: "cancelled" });
});

function cancelButtons() {
  return screen.getAllByRole("button", { name: i18n.t("bookingWaitlist.cancel") });
}

describe("the list", () => {
  it("fetches TODAY by default and renders the rows in the order the server gave", async () => {
    render(<WaitlistSection />);
    await screen.findByText("נועה לוי");
    // The DateField defaults to the Jerusalem today, and the fetch carries it.
    expect(getList).toHaveBeenCalledWith(todayJerusalem());
    const rows = screen.getAllByRole("row").slice(1); // minus the header
    // Row order IS the position (D1): rendered exactly as given, never
    // re-sorted client-side.
    expect(within(rows[0]).getByText("נועה לוי")).toBeInTheDocument();
    // A phone the boutique never booked renders the phone itself.
    expect(within(rows[1]).getByText("+972529998877")).toBeInTheDocument();
    // The status badge speaks Hebrew, never the raw wire value.
    expect(within(rows[0]).getByText(i18n.t("bookingWaitlist.statusWaiting"))).toBeInTheDocument();
    expect(screen.queryByText("waiting")).toBeNull();
  });

  it("clearing the date filter refetches all upcoming days", async () => {
    render(<WaitlistSection />);
    await screen.findByText("נועה לוי");
    fireEvent.change(screen.getByLabelText(i18n.t("bookingWaitlist.dayFilter")), {
      target: { value: "" },
    });
    await waitFor(() => {
      expect(getList).toHaveBeenLastCalledWith(undefined);
    });
  });

  it("renders the empty state, and the filtered-empty line when a date is set", async () => {
    getList.mockResolvedValue({ entries: [] });
    render(<WaitlistSection />);
    // A date IS set by default, so the day may simply have no entries.
    expect(
      await screen.findByText(i18n.t("bookingWaitlist.emptyFiltered")),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(i18n.t("bookingWaitlist.dayFilter")), {
      target: { value: "" },
    });
    expect(await screen.findByText(i18n.t("bookingWaitlist.emptyTitle"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("bookingWaitlist.emptyBody"))).toBeInTheDocument();
  });

  it("renders the honest failure line with a retry that refetches", async () => {
    getList.mockRejectedValueOnce(new Error("down"));
    render(<WaitlistSection />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      i18n.t("bookingWaitlist.loadFailed"),
    );
    fireEvent.click(screen.getByRole("button", { name: i18n.t("bookingWaitlist.retry") }));
    await screen.findByText("נועה לוי");
    expect(getList).toHaveBeenCalledTimes(2);
  });
});

describe("the cancel", () => {
  it("confirms IN PLACE: the second click cancels, refetches, and announces", async () => {
    render(<WaitlistSection />);
    await screen.findByText("נועה לוי");
    fireEvent.click(cancelButtons()[0]);
    // The swap: same slot, danger label, nothing fired yet.
    const confirm = screen.getByRole("button", { name: i18n.t("bookingWaitlist.cancelConfirm") });
    expect(cancelEntry).not.toHaveBeenCalled();

    getList.mockResolvedValue({ entries: [STRANGER] });
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(cancelEntry).toHaveBeenCalledWith("we-1");
    });
    // Refetched: the cancelled row left the table.
    await waitFor(() => {
      expect(screen.queryByText("נועה לוי")).toBeNull();
    });
    // The discrete-event announcement (R16).
    expect(screen.getByTestId("waitlist-section-status").textContent).toBe(
      i18n.t("bookingWaitlist.cancelled"),
    );
  });

  it("Escape reverts the swap without cancelling", async () => {
    render(<WaitlistSection />);
    await screen.findByText("נועה לוי");
    fireEvent.click(cancelButtons()[0]);
    const confirm = screen.getByRole("button", { name: i18n.t("bookingWaitlist.cancelConfirm") });
    fireEvent.keyDown(confirm, { key: "Escape" });
    expect(
      screen.queryByRole("button", { name: i18n.t("bookingWaitlist.cancelConfirm") }),
    ).toBeNull();
    expect(cancelButtons()).toHaveLength(2);
    expect(cancelEntry).not.toHaveBeenCalled();
  });

  it("a second row's cancel is untouched by the first row's swap", async () => {
    render(<WaitlistSection />);
    await screen.findByText("נועה לוי");
    fireEvent.click(cancelButtons()[0]);
    // Exactly ONE confirm control exists — the other row keeps its plain
    // cancel, so a double-armed table cannot cancel the wrong woman.
    expect(
      screen.getAllByRole("button", { name: i18n.t("bookingWaitlist.cancelConfirm") }),
    ).toHaveLength(1);
    expect(cancelButtons()).toHaveLength(1);
  });
});
