import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Reservation } from "../api";
import { ReservationsPane, RESERVATION_BUFFER_DAYS } from "../components/ReservationsPane";

vi.mock("../api", () => ({
  api: {
    listDressReservations: vi.fn(),
    createDressReservation: vi.fn(),
    deleteDressReservation: vi.fn(),
    listCustomers: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    code: string;
    details?: Record<string, string>;
    constructor(status: number, code: string, message: string, details?: Record<string, string>) {
      super(message);
      this.status = status;
      this.code = code;
      this.details = details;
    }
  },
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : "שגיאה"),
}));

const { api, ApiError } = await import("../api");
const listReservations = vi.mocked(api.listDressReservations);
const createReservation = vi.mocked(api.createDressReservation);
const deleteReservation = vi.mocked(api.deleteDressReservation);
const listCustomers = vi.mocked(api.listCustomers);

function reservation(overrides: Partial<Reservation> = {}): Reservation {
  return {
    id: "r1",
    starts_on: "2026-08-12",
    ends_on: "2026-08-18",
    customer_id: null,
    customer_name: null,
    notes: null,
    created_at: "2026-08-01T10:00:00Z",
    ...overrides,
  };
}

function renderPane(props: { dressId?: string | null; disabled?: boolean } = {}) {
  render(
    <ReservationsPane
      dressId={props.dressId === undefined ? "d1" : props.dressId}
      disabled={props.disabled ?? false}
      disabledReason={null}
      disabledHint={null}
    />,
  );
}

function weddingDateInput(): HTMLInputElement {
  return screen.getByLabelText(/תאריך החתונה/) as HTMLInputElement;
}
function startInput(): HTMLInputElement {
  return screen.getByLabelText("מהתאריך") as HTMLInputElement;
}
function endInput(): HTMLInputElement {
  return screen.getByLabelText("עד התאריך (כולל)") as HTMLInputElement;
}

beforeEach(() => {
  vi.clearAllMocks();
  listReservations.mockResolvedValue({ items: [] });
  listCustomers.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 10 });
});

// --- the prefill arithmetic, first: it is the one piece of real logic here ---

describe("wedding-date prefill", () => {
  it("fills the range with the wedding day plus the buffer", async () => {
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(weddingDateInput(), { target: { value: "2026-08-12" } });
    expect(startInput().value).toBe("2026-08-12");
    expect(endInput().value).toBe("2026-08-17");
    expect(RESERVATION_BUFFER_DAYS).toBe(5);
  });

  it("rolls over the end of a month", async () => {
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(weddingDateInput(), { target: { value: "2026-08-29" } });
    expect(endInput().value).toBe("2026-09-03");
  });

  it("rolls over the end of a year", async () => {
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(weddingDateInput(), { target: { value: "2026-12-30" } });
    expect(endInput().value).toBe("2027-01-04");
  });

  it("crosses a leap day in date parts, not milliseconds", async () => {
    // 2028 is a leap year: 26 Feb + 5 is 2 March, not 3.
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(weddingDateInput(), { target: { value: "2028-02-26" } });
    expect(endInput().value).toBe("2028-03-02");
  });

  it("never re-clobbers a range the owner has already touched", async () => {
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(weddingDateInput(), { target: { value: "2026-08-12" } });
    fireEvent.change(endInput(), { target: { value: "2026-08-25" } });
    fireEvent.change(weddingDateInput(), { target: { value: "2026-08-13" } });
    expect(endInput().value).toBe("2026-08-25");
    expect(startInput().value).toBe("2026-08-12");
  });
});

// --- pane contract ---

describe("pane states", () => {
  it("is disabled with the hint in create mode and never calls the api", () => {
    render(
      <ReservationsPane
        dressId={null}
        disabled={true}
        disabledReason="יש לשמור את השמלה תחילה"
        disabledHint="יש לשמור את השמלה לפני הוספת מידות, תמונות והזמנות"
      />,
    );
    expect(
      screen.getByText("יש לשמור את השמלה לפני הוספת מידות, תמונות והזמנות"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /הוספת הזמנה/ })).toBeDisabled();
    expect(listReservations).not.toHaveBeenCalled();
  });

  it("shows the empty state when the dress has no reservations", async () => {
    renderPane();
    expect(await screen.findByText("אין הזמנות לשמלה הזאת.")).toBeInTheDocument();
  });

  it("lists a reservation as a formatted range with its customer and notes", async () => {
    listReservations.mockResolvedValue({
      items: [reservation({ customer_name: "רותם לוי", notes: "חתונה בקיסריה" })],
    });
    renderPane();
    expect(await screen.findByText("12–18")).toBeInTheDocument();
    expect(screen.getByText("רותם לוי")).toBeInTheDocument();
    expect(screen.getByText("חתונה בקיסריה")).toBeInTheDocument();
  });

  it("shows an inline error with a retry when the load fails", async () => {
    listReservations.mockRejectedValue(new Error("boom"));
    renderPane();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הצלחנו לטעון את ההזמנות כרגע.",
    );
    listReservations.mockResolvedValue({ items: [reservation()] });
    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(await screen.findByText("12–18")).toBeInTheDocument();
  });
});

// --- create ---

describe("adding a reservation", () => {
  it("sends the two dates and announces the success without moving focus", async () => {
    createReservation.mockResolvedValue(reservation());
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(weddingDateInput(), { target: { value: "2026-08-12" } });
    const addButton = screen.getByRole("button", { name: /הוספת הזמנה/ });
    addButton.focus();
    fireEvent.click(addButton);
    await waitFor(() =>
      expect(createReservation).toHaveBeenCalledWith("d1", {
        starts_on: "2026-08-12",
        ends_on: "2026-08-17",
        customer_id: null,
        notes: null,
      }),
    );
    expect(await screen.findByText("ההזמנה נוספה.")).toBeInTheDocument();
    // P3: the form is her continuing context — she records several in a row.
    expect(document.activeElement).toBe(addButton);
  });

  it("refuses an inverted range client-side and never calls the api", async () => {
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(startInput(), { target: { value: "2026-08-18" } });
    fireEvent.change(endInput(), { target: { value: "2026-08-12" } });
    fireEvent.click(screen.getByRole("button", { name: /הוספת הזמנה/ }));
    expect(await screen.findByText("תאריך הסיום לפני תאריך ההתחלה")).toBeInTheDocument();
    expect(createReservation).not.toHaveBeenCalled();
  });

  it("refuses a range longer than a year client-side", async () => {
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(startInput(), { target: { value: "2026-08-12" } });
    fireEvent.change(endInput(), { target: { value: "2027-08-13" } });
    fireEvent.click(screen.getByRole("button", { name: /הוספת הזמנה/ }));
    expect(await screen.findByText("טווח ההזמנה ארוך משנה")).toBeInTheDocument();
    expect(createReservation).not.toHaveBeenCalled();
  });

  it("names the conflicting range on a 409 and keeps every value in the form", async () => {
    createReservation.mockRejectedValue(
      new ApiError(409, "RESERVATION_OVERLAP", "clash", {
        starts_on: "2026-08-12",
        ends_on: "2026-08-18",
      }),
    );
    renderPane();
    await waitFor(() => expect(listReservations).toHaveBeenCalled());
    fireEvent.change(startInput(), { target: { value: "2026-08-15" } });
    fireEvent.change(endInput(), { target: { value: "2026-08-20" } });
    fireEvent.click(screen.getByRole("button", { name: /הוספת הזמנה/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("התאריכים מתנגשים עם הזמנה קיימת");
    expect(alert).toHaveTextContent("12–18 באוגוסט");
    // The fix is editing dates, not retyping everything.
    expect(startInput().value).toBe("2026-08-15");
    expect(endInput().value).toBe("2026-08-20");
  });
});

// --- delete ---

describe("deleting a reservation", () => {
  it("confirms in a modal, then removes the row and announces it", async () => {
    listReservations.mockResolvedValue({ items: [reservation()] });
    deleteReservation.mockResolvedValue({ ok: true });
    renderPane();
    fireEvent.click(await screen.findByRole("button", { name: /מחיקה/ }));
    expect(await screen.findByText("למחוק את ההזמנה?")).toBeInTheDocument();
    listReservations.mockResolvedValue({ items: [] });
    fireEvent.click(screen.getByRole("button", { name: "מחיקה", hidden: true }));
    await waitFor(() => expect(deleteReservation).toHaveBeenCalledWith("d1", "r1"));
    expect(await screen.findByText("ההזמנה נמחקה.")).toBeInTheDocument();
  });

  it("keeps the row when the delete fails", async () => {
    listReservations.mockResolvedValue({ items: [reservation()] });
    deleteReservation.mockRejectedValue(new Error("boom"));
    renderPane();
    fireEvent.click(await screen.findByRole("button", { name: /מחיקה/ }));
    fireEvent.click(screen.getByRole("button", { name: "מחיקה", hidden: true }));
    await waitFor(() => expect(deleteReservation).toHaveBeenCalled());
    expect(await screen.findByText("12–18")).toBeInTheDocument();
  });
});
