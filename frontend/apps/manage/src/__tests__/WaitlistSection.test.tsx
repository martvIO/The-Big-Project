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
    offer_starts_at: null,
    offer_expires_at: null,
    ...overrides,
  };
}

// F23. The one row shape the offer column exists for: a bride holding a live
// offer on 20.8 at 14:30 Jerusalem, until 12:15.
const OFFERED = row({
  id: "we-3",
  customer_name: "רותם לוי",
  status: "offered",
  offer_starts_at: "2026-08-20T11:30:00Z",
  offer_expires_at: "2026-08-20T09:15:00Z",
});

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

  it("names the CONSEQUENCE when the armed row is holding a live offer", async () => {
    // Design §4. Cancelling an `offered` row kills an offer a bride may be
    // holding this second, and the generic «אישור הביטול» does not say so. The
    // owner is one click from removing a woman who is reading her SMS.
    getList.mockResolvedValue({ entries: [OFFERED, row()] });
    render(<WaitlistSection />);
    await screen.findByText("רותם לוי");

    fireEvent.click(cancelButtons()[0]);

    expect(
      screen.getByRole("button", { name: i18n.t("bookingWaitlist.cancelOfferedConfirm") }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: i18n.t("bookingWaitlist.cancelConfirm") }),
    ).toBeNull();
  });

  it("keeps the generic danger label on a waiting row", async () => {
    // The pair to the above: the two labels must actually differ per row, or
    // the consequence sentence is decoration.
    getList.mockResolvedValue({ entries: [OFFERED, row()] });
    render(<WaitlistSection />);
    await screen.findByText("רותם לוי");

    fireEvent.click(cancelButtons()[1]);

    expect(
      screen.getByRole("button", { name: i18n.t("bookingWaitlist.cancelConfirm") }),
    ).toBeInTheDocument();
    expect(
      i18n.t("bookingWaitlist.cancelOfferedConfirm"),
    ).not.toBe(i18n.t("bookingWaitlist.cancelConfirm"));
  });
});

describe("the offer column", () => {
  it("names the held slot and its deadline, both LTR-isolated", async () => {
    // The ONE thing an owner needs from an offered row: is anyone holding this
    // slot right now, and until when.
    getList.mockResolvedValue({ entries: [OFFERED] });
    render(<WaitlistSection />);
    await screen.findByText("רותם לוי");

    expect(screen.getByText(i18n.t("bookingWaitlist.colOffer"))).toBeInTheDocument();
    // 11:30Z is 14:30 Jerusalem; 09:15Z is 12:15. Asserted as Jerusalem wall
    // clock rather than as the wire instant — an owner reads the shop's clock.
    const slot = screen.getByText("14:30");
    const expiry = screen.getByText("12:15");
    for (const node of [slot, expiry]) {
      expect(node.tagName).toBe("BDI");
      expect(node).toHaveAttribute("dir", "ltr");
    }
    // R19's lead-then-island shape, not one interpolated sentence.
    expect(expiry.parentElement).toHaveTextContent(i18n.t("bookingWaitlist.offerUntil"));
  });

  it("renders an em dash for a row holding no offer", async () => {
    getList.mockResolvedValue({ entries: [OFFERED, row()] });
    render(<WaitlistSection />);
    await screen.findByText("רותם לוי");

    const rows = screen.getAllByRole("row").slice(1);
    // Column index 4: day, type, customer, status, OFFER, joined, action.
    expect(within(rows[1]).getAllByRole("cell")[4].textContent).toBe("—");
    // And the waiting row must not borrow the offered row's deadline.
    expect(within(rows[1]).queryByText("12:15")).toBeNull();
  });

  it("marks the offered badge as in-flight, not as a neutral steady state", async () => {
    // P4. F22 shipped `neutral` as a placeholder for a status that could not
    // yet occur. Now that it can, the row an owner must not casually cancel has
    // to separate from the ones that are merely waiting.
    getList.mockResolvedValue({ entries: [OFFERED, row()] });
    render(<WaitlistSection />);
    await screen.findByText("רותם לוי");

    const rows = screen.getAllByRole("row").slice(1);
    const offered = within(rows[0]).getByText(i18n.t("bookingWaitlist.statusOffered"));
    const waiting = within(rows[1]).getByText(i18n.t("bookingWaitlist.statusWaiting"));
    // The variant is asserted through the class the Badge actually paints, so a
    // prop renamed out from under this test cannot pass silently.
    expect(offered.className).not.toBe(waiting.className);
    expect(offered.className).toMatch(/warning/);
  });

  it("does NOT tick — the deadline is a fact, not a timer", async () => {
    // The manage half of R1. An owner's table is the other place a countdown
    // would have been tempting, and it is banned here for the same reason.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      getList.mockResolvedValue({ entries: [OFFERED] });
      const { container } = render(<WaitlistSection />);
      await screen.findByText("רותם לוי");
      const before = container.innerHTML;

      await vi.advanceTimersByTimeAsync(120_000);

      expect(container.innerHTML).toBe(before);
      // No poll either: a waitlist changes at human speed (F22's ceiling).
      expect(getList).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
