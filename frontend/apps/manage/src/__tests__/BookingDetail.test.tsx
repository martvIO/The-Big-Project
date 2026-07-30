import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { OwnerBookingDetail, OwnerBookingListResponse, OwnerBookingRow } from "../api";
import { BookingDetail } from "../components/BookingDetail";
import { BookingsSection } from "../components/BookingsSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      listBookings: vi.fn(),
      getBooking: vi.fn(),
      confirmBooking: vi.fn(),
      cancelBooking: vi.fn(),
      noShowBooking: vi.fn(),
      completeBooking: vi.fn(),
      rescheduleBooking: vi.fn(),
      correctBookingPhone: vi.fn(),
      resendBookingLink: vi.fn(),
      listManageSlots: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const listBookings = vi.mocked(api.listBookings);
const getBooking = vi.mocked(api.getBooking);
const cancelBooking = vi.mocked(api.cancelBooking);
const noShowBooking = vi.mocked(api.noShowBooking);
const completeBooking = vi.mocked(api.completeBooking);
const confirmBooking = vi.mocked(api.confirmBooking);
const correctBookingPhone = vi.mocked(api.correctBookingPhone);
const resendBookingLink = vi.mocked(api.resendBookingLink);

// Three of the four transitions are clock-guarded, so the fixtures sit either
// side of "now" by construction rather than by faking the clock — the same
// trick test_booking_repositories.py plays with its 2099 constants. 07:00Z in
// August is 10:00 in Jerusalem and 03:00 in New York, which is what this
// runner's TZ pin says.
const FUTURE = "2099-08-04T07:00:00Z";
const PAST = "2020-08-04T05:00:00Z";

function detail(overrides: Partial<OwnerBookingDetail> = {}): OwnerBookingDetail {
  return {
    id: "b1",
    starts_at: FUTURE,
    status: "confirmed",
    attendance_confirmed_at: null,
    customer_name: "מיכל לוי",
    appointment_type_name: "מדידה ראשונה",
    dress_name: "שמלת אלמה",
    customer_phone: "+972501234567",
    notes: "באה עם אמא ואחות, מגיעות מחיפה",
    dress_id: "d1",
    dress_size: "36",
    seat_index: 2,
    created_at: "2099-08-01T06:12:00Z",
    terms_version_accepted: 3,
    terms_accepted_at: "2099-08-01T06:12:00Z",
    cancelled_at: null,
    cancelled_by: null,
    manage_link_issued: true,
    ...overrides,
  };
}

function listRow(overrides: Partial<OwnerBookingRow> = {}): OwnerBookingListResponse {
  return {
    items: [
      {
        id: "b1",
        starts_at: FUTURE,
        status: "confirmed",
        attendance_confirmed_at: null,
        customer_name: "מיכל לוי",
        appointment_type_name: "מדידה ראשונה",
        dress_name: "שמלת אלמה",
        ...overrides,
      },
    ],
    total: 1,
    offset: 0,
    limit: 50,
  };
}

function mount(overrides: Partial<OwnerBookingDetail> = {}) {
  getBooking.mockResolvedValue(detail(overrides));
  return render(
    <BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />,
  );
}

// BookingDetail replaces the list inside ConsoleShell's <main>, which owns the
// console's single sr-only <h1>. The axe harness reproduces that frame.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

function dialogOf(title: string): HTMLElement {
  const found = screen.getByRole("heading", { name: title }).closest("dialog");
  if (found === null) {
    throw new Error(`no <dialog> around «${title}»`);
  }
  return found;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("BookingDetail load states", () => {
  it("DL-load — the heading takes focus and the status region announces the load", () => {
    getBooking.mockReturnValue(new Promise(() => {}));
    render(<BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />);

    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("פרטי התור");
    expect(heading).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("טוען את פרטי התור…");
    expect(screen.queryByText("הלקוחה")).toBeNull();
  });

  it("DL-404 — an alert, no facts, and the back control still reachable", async () => {
    getBooking.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    render(<BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("התור הזה לא נמצא.");
    expect(screen.getByRole("button", { name: "חזרה לרשימה" })).toBeInTheDocument();
    expect(screen.queryByText("הלקוחה")).toBeNull();
    // Another tenant's id 404s too, by RLS design — never the API's English.
    expect(screen.queryByText("Resource not found.")).toBeNull();
  });

  it("never puts the bride's name in the announced heading", async () => {
    mount();
    await screen.findByText("הלקוחה");

    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("פרטי התור");
    expect(heading).not.toHaveTextContent("מיכל לוי");
    // …and the name is the first fact row, one line below.
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
  });
});

describe("BookingDetail facts", () => {
  it("renders three fact groups plus the actions group, all h3, no skipped level", async () => {
    mount();
    await screen.findByText("הלקוחה");

    expect(screen.getAllByRole("heading", { level: 3 }).map((node) => node.textContent)).toEqual([
      "הלקוחה",
      "הפגישה",
      "הערות הלקוחה",
      "פעולות",
    ]);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
  });

  it('isolates every numeric run with <bdi dir="ltr">', async () => {
    mount();
    await screen.findByText("הלקוחה");

    // phone, appointment date, appointment time, dress size, seat, terms version
    for (const value of ["+972501234567", "4.8.2099", "10:00", "36", "2", "3"]) {
      const node = screen.getAllByText(value)[0];
      expect(node.tagName).toBe("BDI");
      expect(node).toHaveAttribute("dir", "ltr");
    }
  });

  it('leaves free text in a BARE bdi — dir="ltr" on Hebrew is the worse defect', async () => {
    mount();
    await screen.findByText("הלקוחה");

    for (const value of ["מיכל לוי", "שמלת אלמה", "באה עם אמא ואחות, מגיעות מחיפה"]) {
      const node = screen.getByText(value);
      expect(node.tagName).toBe("BDI");
      expect(node).not.toHaveAttribute("dir");
    }
  });

  it("renders notes as TEXT and only text — never innerHTML, markdown or a link", async () => {
    mount({ notes: "<script>alert(1)</script>\nhttps://evil.example" });
    await screen.findByText("הערות הלקוחה");

    const notes = screen.getByTestId("booking-notes");
    // The tags are characters on the page, not elements in the tree.
    expect(notes.textContent).toBe("<script>alert(1)</script>\nhttps://evil.example");
    expect(notes.querySelector("script")).toBeNull();
    expect(notes.querySelector("a")).toBeNull();
    // Her line breaks survive without a markdown pass.
    expect(notes.querySelector("bdi")).not.toBeNull();
    expect(notes).toHaveClass("whitespace-pre-wrap");
  });

  it("says so when there are no notes", async () => {
    mount({ notes: null });
    expect(await screen.findByText("הלקוחה לא הוסיפה הערות.")).toBeInTheDocument();
  });

  it("renders manage_link_issued as words, never a chip", async () => {
    mount({ manage_link_issued: true });
    await screen.findByText("הלקוחה");

    expect(screen.getByText("קישור ניהול פעיל")).toBeInTheDocument();
    // Exactly one Badge on the screen, and it is the status.
    expect(screen.getAllByTestId("booking-status")).toHaveLength(1);
  });

  it("renders the missing-link wording when no link was ever issued", async () => {
    mount({ manage_link_issued: false });
    expect(await screen.findByText("לא הונפק קישור ניהול")).toBeInTheDocument();
  });

  it("hides cancelled_at / cancelled_by on a live booking", async () => {
    mount();
    await screen.findByText("הלקוחה");
    expect(screen.queryByText("בוטל בתאריך")).toBeNull();
    expect(screen.queryByText("בוטל על ידי")).toBeNull();
  });

  it("shows cancelled_at / cancelled_by on a cancelled one", async () => {
    mount({
      status: "cancelled",
      cancelled_at: "2099-08-02T09:00:00Z",
      cancelled_by: "owner",
    });
    await screen.findByText("הלקוחה");

    expect(screen.getByText("בוטל בתאריך")).toBeInTheDocument();
    expect(screen.getByText("בוטל על ידי")).toBeInTheDocument();
    expect(screen.getByText("הבוטיק")).toBeInTheDocument();
  });
});

describe("BookingDetail transition controls — absent, never disabled", () => {
  const RESCHEDULE = "שינוי מועד";
  const RESEND = "הנפקת קישור ניהול חדש";
  const PHONE = "תיקון מספר הטלפון";
  const CANCEL = "ביטול התור";
  const NO_SHOW = "סימון: לא הגיעה";
  const COMPLETE = "סימון: התקיים";
  const REOPEN = "החזרה לסטטוס מאושר";
  const ALL = [RESCHEDULE, RESEND, PHONE, CANCEL, NO_SHOW, COMPLETE, REOPEN];

  async function controlsFor(overrides: Partial<OwnerBookingDetail>) {
    mount(overrides);
    await screen.findByText("הלקוחה");
    return ALL.filter((name) => screen.queryByRole("button", { name }) !== null);
  }

  it("confirmed and future — move, reissue, correct the phone, cancel", async () => {
    expect(await controlsFor({ status: "confirmed", starts_at: FUTURE })).toEqual([
      RESCHEDULE,
      RESEND,
      PHONE,
      CANCEL,
    ]);
  });

  it("confirmed and past — the two attendance outcomes, and NO error affordance", async () => {
    // D3: "confirmed and past, never marked" is not an error state (Risk 8), so
    // it is rendered as silence — no nag, no warning.
    expect(await controlsFor({ status: "confirmed", starts_at: PAST })).toEqual([
      NO_SHOW,
      COMPLETE,
    ]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("no_show — complete, and the undo", async () => {
    expect(await controlsFor({ status: "no_show", starts_at: PAST })).toEqual([COMPLETE, REOPEN]);
  });

  it("completed — no-show, and the undo", async () => {
    expect(await controlsFor({ status: "completed", starts_at: PAST })).toEqual([
      NO_SHOW,
      REOPEN,
    ]);
  });

  it("cancelled — no controls at all, and the storefront named as the remedy", async () => {
    expect(await controlsFor({ status: "cancelled", starts_at: FUTURE })).toEqual([]);
    expect(
      screen.getByText(
        "תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
      ),
    ).toBeInTheDocument();
    // Nothing will be sent, so the standing delivery limit is not stated either.
    expect(screen.queryByText(/אין באפשרותנו לאמת/)).toBeNull();
  });

  it("carries the standing delivery notice wherever actions exist", async () => {
    mount();
    expect(
      await screen.findByText(
        "אין באפשרותנו לאמת שהודעות נמסרו ללקוחה. אם חשוב לוודא, אפשר להתקשר אליה.",
      ),
    ).toBeInTheDocument();
  });
});

describe("BookingDetail destructive trigger", () => {
  it("is a solid danger Button, never ghost + a text-danger className", async () => {
    mount();
    const trigger = await screen.findByRole("button", { name: "ביטול התור" });

    // design F-6: cn() is a plain join and the built CSS emits .text-danger
    // before .text-ink, so ghost's text-ink would win and the destructive
    // affordance would silently disappear.
    expect(trigger).toHaveClass("bg-danger");
    expect(trigger).not.toHaveClass("text-danger");
    expect(trigger).not.toHaveClass("bg-transparent");
  });
});

describe("BookingDetail cancel Modal", () => {
  it("confirms before cancelling, and states that it is final", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "ביטול התור" }));

    const dialog = dialogOf("לבטל את התור?");
    expect(dialog).toHaveTextContent(
      "הביטול סופי ואי אפשר לשחזר אותו. המועד יתפנה להזמנה, ולקביעת מועד חדש הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
    );
    // Opening the dialog is not the act.
    expect(cancelBooking).not.toHaveBeenCalled();

    cancelBooking.mockResolvedValue(
      detail({ status: "cancelled", cancelled_at: FUTURE, cancelled_by: "owner" }),
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "אישור הביטול" }));

    await waitFor(() => expect(cancelBooking).toHaveBeenCalledWith("b1"));
    expect(await screen.findByText("התור בוטל.")).toBeInTheDocument();
    // The whole detail re-renders from the response, so the controls go with it.
    expect(screen.queryByRole("button", { name: "ביטול התור" })).toBeNull();
  });

  it("restores focus to the trigger on dismiss — native return lands on <body>", async () => {
    mount();
    const trigger = await screen.findByRole("button", { name: "ביטול התור" });
    fireEvent.click(trigger);

    fireEvent.click(within(dialogOf("לבטל את התור?")).getByRole("button", { name: "חזרה" }));

    await waitFor(() => expect(trigger).toHaveFocus());
    expect(cancelBooking).not.toHaveBeenCalled();
  });
});

describe("BookingDetail attendance outcomes", () => {
  it("marks no-show and moves focus to the announced cue", async () => {
    mount({ status: "confirmed", starts_at: PAST });
    noShowBooking.mockResolvedValue(detail({ status: "no_show", starts_at: PAST }));

    fireEvent.click(await screen.findByRole("button", { name: "סימון: לא הגיעה" }));

    expect(await screen.findByText("התור סומן: לא הגיעה.")).toBeInTheDocument();
    // A successful transition can unmount the very control that was clicked, so
    // focus must never be allowed to drop to <body>.
    await waitFor(() => expect(screen.getByRole("status")).toHaveFocus());
  });

  it("marks completed", async () => {
    mount({ status: "confirmed", starts_at: PAST });
    completeBooking.mockResolvedValue(detail({ status: "completed", starts_at: PAST }));

    fireEvent.click(await screen.findByRole("button", { name: "סימון: התקיים" }));

    expect(await screen.findByText("התור סומן: התקיים.")).toBeInTheDocument();
  });

  it("undoes a mis-tap back to confirmed", async () => {
    mount({ status: "no_show", starts_at: PAST });
    confirmBooking.mockResolvedValue(detail({ status: "confirmed", starts_at: PAST }));

    fireEvent.click(await screen.findByRole("button", { name: "החזרה לסטטוס מאושר" }));

    expect(await screen.findByText("הסטטוס הוחזר למאושר.")).toBeInTheDocument();
    expect(screen.getByTestId("booking-status")).toHaveTextContent("מאושר");
  });

  it("disables every action while one is in flight", async () => {
    mount({ status: "confirmed", starts_at: PAST });
    completeBooking.mockReturnValue(new Promise(() => {}));

    fireEvent.click(await screen.findByRole("button", { name: "סימון: התקיים" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "סימון: התקיים" })).toBeDisabled(),
    );
    expect(screen.getByRole("button", { name: "סימון: לא הגיעה" })).toBeDisabled();
  });
});

describe("BookingDetail resend", () => {
  it("warns BEFORE the tap that the old link dies, and repeats it after", async () => {
    mount();
    await screen.findByText("פעולות");

    // Permanent and pre-tap — resend gets no confirm Modal (D9).
    expect(
      screen.getByText("הנפקת קישור חדש מבטלת את הקישור הקודם של הלקוחה."),
    ).toBeInTheDocument();

    resendBookingLink.mockResolvedValue(detail());
    fireEvent.click(screen.getByRole("button", { name: "הנפקת קישור ניהול חדש" }));

    expect(await screen.findByText("הונפק קישור חדש. הקישור הקודם בוטל.")).toBeInTheDocument();
    // Still readable for the next tap.
    expect(
      screen.getByText("הנפקת קישור חדש מבטלת את הקישור הקודם של הלקוחה."),
    ).toBeInTheDocument();
  });

  it("disables the button while its request is in flight — the double-tap mitigation", async () => {
    mount();
    resendBookingLink.mockReturnValue(new Promise(() => {}));

    fireEvent.click(await screen.findByRole("button", { name: "הנפקת קישור ניהול חדש" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "הנפקת קישור ניהול חדש" })).toBeDisabled(),
    );
    expect(resendBookingLink).toHaveBeenCalledTimes(1);
  });
});

describe("BookingDetail phone correction", () => {
  async function openField() {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "תיקון מספר הטלפון" }));
    return screen.getByLabelText("מספר טלפון חדש");
  }

  it("opens EMPTY — a pre-filled wrong number invites a one-character edit", async () => {
    const field = await openField();
    expect(field).toHaveValue("");
    expect(field).toHaveAttribute("dir", "ltr");
    expect(field).toHaveAttribute("type", "tel");
    expect(field).toHaveAttribute("inputmode", "tel");
  });

  it("carries no client-side validation of any kind — the server's 400 is the authority", async () => {
    const field = await openField();
    fireEvent.change(field, { target: { value: "not a phone" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המספר" }));

    correctBookingPhone.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "phone: not a valid Israeli mobile number"),
    );
    fireEvent.click(
      within(dialogOf("לעדכן את מספר הטלפון?")).getByRole("button", { name: "עדכון המספר" }),
    );

    // It was POSTed exactly as typed — no normalizer, no pattern, no length rule.
    await waitFor(() => expect(correctBookingPhone).toHaveBeenCalledWith("b1", "not a phone"));
    // …and the server's message renders in the field's own error slot.
    expect(
      await screen.findByText("phone: not a valid Israeli mobile number"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("מספר טלפון חדש")).toHaveAttribute("aria-invalid", "true");
  });

  it("echoes the typed number in the confirm Modal, isolated LTR, with no verification claim", async () => {
    const field = await openField();
    fireEvent.change(field, { target: { value: "050-999-8888" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המספר" }));

    const dialog = dialogOf("לעדכן את מספר הטלפון?");
    const echoed = within(dialog).getByText("050-999-8888");
    expect(echoed.tagName).toBe("BDI");
    expect(echoed).toHaveAttribute("dir", "ltr");
    expect(dialog).toHaveTextContent("המערכת אינה מאמתת שהמספר שייך ללקוחה");
    expect(dialog).toHaveTextContent("הקישור הקיים של הלקוחה יפסיק לעבוד");
    // Nothing is written until the confirm.
    expect(correctBookingPhone).not.toHaveBeenCalled();
  });

  it("commits the correction and closes the field", async () => {
    const field = await openField();
    fireEvent.change(field, { target: { value: "0509998888" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המספר" }));

    correctBookingPhone.mockResolvedValue(detail({ customer_phone: "+972509998888" }));
    fireEvent.click(
      within(dialogOf("לעדכן את מספר הטלפון?")).getByRole("button", { name: "עדכון המספר" }),
    );

    expect(await screen.findByText("מספר הטלפון עודכן. הקישור הקודם בוטל.")).toBeInTheDocument();
    expect(screen.getByText("+972509998888")).toBeInTheDocument();
    expect(screen.queryByLabelText("מספר טלפון חדש")).toBeNull();
  });

  it("restores focus to its trigger when the confirm Modal is dismissed", async () => {
    await openField();
    const trigger = screen.getByRole("button", { name: "שמירת המספר" });
    fireEvent.click(trigger);

    fireEvent.click(
      within(dialogOf("לעדכן את מספר הטלפון?")).getByRole("button", { name: "חזרה" }),
    );

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("is not offered on a booking the graph will not let it touch", async () => {
    mount({ status: "confirmed", starts_at: PAST });
    await screen.findByText("הלקוחה");
    expect(screen.queryByRole("button", { name: "תיקון מספר הטלפון" })).toBeNull();
  });
});

describe("BookingDetail error rendering", () => {
  it("renders Hebrew for the codes F15 owns, never main.py's English", async () => {
    const cases: [string, string][] = [
      [
        "BOOKING_TRANSITION_INVALID",
        "לא ניתן לבצע את הפעולה במצב הנוכחי של התור. כדאי לחזור לרשימה ולפתוח את התור מחדש.",
      ],
      ["TOO_MANY_ATTEMPTS", "בוצעו יותר מדי פעולות בזמן קצר. כדאי להמתין מעט ולנסות שוב."],
      ["CUSTOMER_ALREADY_BOOKED", "ללקוחה כבר יש תור פעיל במועד הזה."],
      ["SLOT_UNAVAILABLE", "המועד הזה נתפס הרגע. אפשר לבחור מועד אחר."],
    ];

    for (const [code, hebrew] of cases) {
      vi.clearAllMocks();
      mount();
      resendBookingLink.mockRejectedValue(new ApiError(409, code, "English body from main.py."));
      fireEvent.click(await screen.findByRole("button", { name: "הנפקת קישור ניהול חדש" }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(hebrew);
      expect(alert).not.toHaveTextContent("English body from main.py.");
      // The fix-this register, not the outage one.
      expect(alert).toHaveClass("text-danger");
      cleanup();
    }
  });

  it("falls through to the server's own message for every other code", async () => {
    mount({ status: "confirmed", starts_at: PAST });
    completeBooking.mockRejectedValue(
      // VALIDATION_ERROR's message is computed per field and cannot be
      // reproduced client-side, so it deliberately is NOT in the map.
      new ApiError(400, "VALIDATION_ERROR", "starts_at: must be an aware datetime"),
    );

    fireEvent.click(await screen.findByRole("button", { name: "סימון: התקיים" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "starts_at: must be an aware datetime",
    );
  });

  it("a 409 leaves the previously-rendered facts exactly where they were", async () => {
    mount({ status: "confirmed", starts_at: PAST });
    noShowBooking.mockRejectedValue(
      new ApiError(409, "BOOKING_TRANSITION_INVALID", "Not allowed."),
    );

    fireEvent.click(await screen.findByRole("button", { name: "סימון: לא הגיעה" }));

    await screen.findByRole("alert");
    // The console never guesses a new state from an error.
    expect(screen.getByTestId("booking-status")).toHaveTextContent("מאושר");
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "סימון: התקיים" })).toBeEnabled();
  });
});

describe("BookingsSection detail hand-off", () => {
  it("swaps the panel in place and patches the row from the mutation response", async () => {
    listBookings.mockResolvedValue(listRow());
    getBooking.mockResolvedValue(detail());
    cancelBooking.mockResolvedValue(
      detail({ status: "cancelled", cancelled_at: FUTURE, cancelled_by: "owner" }),
    );

    render(<BookingsSection />);
    fireEvent.click(await screen.findByRole("button", { name: /מיכל לוי/ }));

    await screen.findByText("הלקוחה");
    fireEvent.click(screen.getByRole("button", { name: "ביטול התור" }));
    fireEvent.click(
      within(dialogOf("לבטל את התור?")).getByRole("button", { name: "אישור הביטול" }),
    );
    await screen.findByText("התור בוטל.");

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));

    // One list fetch for the whole flow — the row is patched from the response,
    // so the two views cannot disagree.
    expect(await screen.findByText("בוטל")).toBeInTheDocument();
    expect(listBookings).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("bookings-count")).toHaveTextContent("תורים ביום זה: 1");
  });

  it("goes back to the list without refetching the day", async () => {
    listBookings.mockResolvedValue(listRow());
    getBooking.mockResolvedValue(detail());

    render(<BookingsSection />);
    fireEvent.click(await screen.findByRole("button", { name: /מיכל לוי/ }));
    await screen.findByText("הלקוחה");

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));

    expect(await screen.findByTestId("bookings-count")).toHaveTextContent("תורים ביום זה: 1");
    expect(screen.getByLabelText("תאריך")).toBeInTheDocument();
    expect(listBookings).toHaveBeenCalledTimes(1);
  });
});

describe("BookingDetail accessibility", () => {
  it("passes axe with zero violations on a live booking", async () => {
    getBooking.mockResolvedValue(detail());
    const { container } = renderInShell(
      <BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />,
    );
    await screen.findByText("הלקוחה");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations with the phone field revealed", async () => {
    getBooking.mockResolvedValue(detail());
    const { container } = renderInShell(
      <BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "תיקון מספר הטלפון" }));

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on a cancelled booking", async () => {
    getBooking.mockResolvedValue(
      detail({
        status: "cancelled",
        cancelled_at: "2099-08-02T09:00:00Z",
        cancelled_by: "customer",
      }),
    );
    const { container } = renderInShell(
      <BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />,
    );
    // «הלקוחה» is ambiguous here: it is both the customer group's h3 and the
    // value of booking.cancelledByCustomer.
    await screen.findByRole("heading", { name: "הפגישה" });

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);
});
