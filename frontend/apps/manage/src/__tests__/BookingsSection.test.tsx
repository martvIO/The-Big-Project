import type { ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { OwnerBookingListResponse, OwnerBookingRow } from "../api";
import { BookingsSection } from "../components/BookingsSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      listBookings: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const listBookings = vi.mocked(api.listBookings);

function row(overrides: Partial<OwnerBookingRow> = {}): OwnerBookingRow {
  return {
    id: "b1",
    // 07:00Z is 10:00 in Jerusalem, 03:00 in New York — and the test script pins
    // TZ=America/New_York, so an unzoned read would print 03:00.
    starts_at: "2026-08-04T07:00:00Z",
    status: "confirmed",
    attendance_confirmed_at: null,
    checked_in_at: null,
    customer_name: "מיכל לוי",
    appointment_type_name: "מדידה ראשונה",
    dress_name: "שמלת אלמה",
    ...overrides,
  };
}

function day(items: OwnerBookingRow[], total = items.length): OwnerBookingListResponse {
  return { items, total, offset: 0, limit: 50 };
}

// BookingsSection renders inside ConsoleShell's <main>, which owns the console's
// single sr-only <h1>. The axe harness reproduces that frame rather than
// scanning a headless fragment.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("BookingsSection day filter", () => {
  it("defaults to the JERUSALEM calendar date, not the device's", () => {
    // 21:30Z on the 4th is 00:30 on the 5th in Jerusalem and 17:30 on the 4th in
    // New York, which is what this runner's clock says.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-04T21:30:00Z"));
    listBookings.mockReturnValue(new Promise(() => {}));

    render(<BookingsSection />);

    expect(listBookings).toHaveBeenCalledWith({ date: "2026-08-05", offset: 0, limit: 50 });
    expect(screen.getByLabelText("תאריך")).toHaveValue("2026-08-05");
  });

  it("refetches the day when the date changes", async () => {
    listBookings.mockResolvedValue(day([row()]));
    render(<BookingsSection />);
    await screen.findByText("מיכל לוי");

    listBookings.mockResolvedValue(day([]));
    fireEvent.change(screen.getByLabelText("תאריך"), { target: { value: "2026-08-09" } });

    await waitFor(() =>
      expect(listBookings).toHaveBeenLastCalledWith({
        date: "2026-08-09",
        offset: 0,
        limit: 50,
      }),
    );
  });

  it("is an LTR island with a visible label", () => {
    listBookings.mockReturnValue(new Promise(() => {}));
    render(<BookingsSection />);

    const field = screen.getByLabelText("תאריך");
    expect(field).toHaveAttribute("type", "date");
    expect(field).toHaveAttribute("dir", "ltr");
  });
});

describe("BookingsSection states", () => {
  it("L-load — the count line announces loading and a Skeleton stands in", () => {
    listBookings.mockReturnValue(new Promise(() => {}));
    render(<BookingsSection />);

    // The shipped console announces nothing while loading; F15 closes that for
    // itself by reusing the region the count needs anyway (design F-1).
    expect(screen.getByRole("status")).toHaveTextContent("טוען תורים…");
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("L-fail — an alert in the OUTAGE register, and no retry control", async () => {
    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "Service unavailable."));
    render(<BookingsSection />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("לא הצלחנו לטעון את התורים כרגע.");
    // Outage, not blame: muted, never text-danger.
    expect(alert).toHaveClass("text-ink-muted");
    expect(screen.queryByRole("button")).toBeNull();
    // No half-loaded list and no empty state stacked under the alert.
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByText("אין תורים בתאריך הזה")).toBeNull();
  });

  it("L-empty — an EmptyState with no CTA, and a count line that reads zero", async () => {
    listBookings.mockResolvedValue(day([], 0));
    render(<BookingsSection />);

    expect(await screen.findByText("אין תורים בתאריך הזה")).toBeInTheDocument();
    expect(screen.getByText("אפשר לבחור תאריך אחר.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("תורים ביום זה: 0");
    // The owner cannot create a booking (Q6), so an action prompt would point
    // at nothing.
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("L — one row button per booking, in the server's order", async () => {
    listBookings.mockResolvedValue(
      day([
        row({ id: "b1", starts_at: "2026-08-04T07:00:00Z", customer_name: "מיכל לוי" }),
        row({ id: "b2", starts_at: "2026-08-04T08:30:00Z", customer_name: "נועה כהן" }),
        row({ id: "b3", starts_at: "2026-08-04T11:00:00Z", customer_name: "שיר אברהם" }),
      ]),
    );
    render(<BookingsSection />);

    await screen.findByText("מיכל לוי");
    expect(screen.getByRole("status")).toHaveTextContent("תורים ביום זה: 3");

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    // One affordance per row: the whole row is the button.
    for (const item of rows) {
      expect(within(item).getAllByRole("button")).toHaveLength(1);
    }
    // The client never re-sorts — the order is the server's (starts_at, seat).
    expect(rows.map((item) => item.textContent)).toEqual([
      expect.stringContaining("מיכל לוי"),
      expect.stringContaining("נועה כהן"),
      expect.stringContaining("שיר אברהם"),
    ]);
  });

  it("renders the time in the Jerusalem calendar, isolated LTR", async () => {
    listBookings.mockResolvedValue(day([row({ starts_at: "2026-08-04T07:00:00Z" })]));
    render(<BookingsSection />);

    const time = await screen.findByText("10:00");
    expect(time.tagName).toBe("BDI");
    expect(time).toHaveAttribute("dir", "ltr");
  });

  it("wraps the customer and dress names in a BARE bdi", async () => {
    listBookings.mockResolvedValue(day([row()]));
    render(<BookingsSection />);

    // dir="ltr" on Hebrew free text is itself a bidi defect.
    const name = await screen.findByText("מיכל לוי");
    expect(name.tagName).toBe("BDI");
    expect(name).not.toHaveAttribute("dir");
    const dress = screen.getByText("שמלת אלמה");
    expect(dress.tagName).toBe("BDI");
    expect(dress).not.toHaveAttribute("dir");
  });

  it("renders attendance as muted words on the meta line, never a second Badge", async () => {
    listBookings.mockResolvedValue(
      day([row({ attendance_confirmed_at: "2026-08-03T09:00:00Z" })]),
    );
    render(<BookingsSection />);

    await screen.findByText("מיכל לוי");
    expect(screen.getByText(/אישרה הגעה/)).toBeInTheDocument();
    // Exactly one Badge per row, and it is the status.
    const item = screen.getByRole("listitem");
    expect(within(item).getAllByTestId("booking-status")).toHaveLength(1);
  });
});

describe("BookingsSection status badges", () => {
  it("maps every status to its Hebrew word — colour is never the signal", async () => {
    listBookings.mockResolvedValue(
      day([
        row({ id: "b1", status: "confirmed", customer_name: "א" }),
        row({ id: "b2", status: "completed", customer_name: "ב" }),
        row({ id: "b3", status: "no_show", customer_name: "ג" }),
        row({ id: "b4", status: "cancelled", customer_name: "ד" }),
      ]),
    );
    render(<BookingsSection />);

    await screen.findByText("מאושר");
    // The WORD is asserted, not the class: the mapping has to survive greyscale.
    expect(screen.getAllByTestId("booking-status").map((node) => node.textContent)).toEqual([
      "מאושר",
      "התקיים",
      "לא הגיעה",
      "בוטל",
    ]);
  });

  it("keeps cancelled rows in the list (D17) and demotes them no further than the badge", async () => {
    listBookings.mockResolvedValue(
      day([row({ id: "b1", status: "cancelled", customer_name: "נועה כהן" })]),
    );
    render(<BookingsSection />);

    // A cancelled row is the owner's evidence that the slot re-opened.
    expect(await screen.findByText("נועה כהן")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent("תורים ביום זה: 1");
  });
});

describe("BookingsSection accessibility", () => {
  it("passes axe with zero violations on the loaded list", async () => {
    listBookings.mockResolvedValue(
      day([
        row({ id: "b1", status: "confirmed", attendance_confirmed_at: "2026-08-03T09:00:00Z" }),
        row({ id: "b2", status: "cancelled", customer_name: "נועה כהן", dress_name: null }),
      ]),
    );
    const { container } = renderInShell(<BookingsSection />);
    await screen.findByText("מיכל לוי");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the empty day", async () => {
    listBookings.mockResolvedValue(day([], 0));
    const { container } = renderInShell(<BookingsSection />);
    await screen.findByText("אין תורים בתאריך הזה");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("puts the section under a single h2 with no skipped level", async () => {
    listBookings.mockResolvedValue(day([row()]));
    render(<BookingsSection />);
    await screen.findByText("מיכל לוי");

    const headings = screen.getAllByRole("heading");
    expect(headings).toHaveLength(1);
    expect(headings[0].tagName).toBe("H2");
    expect(headings[0]).toHaveTextContent("תורים");
  });
});
