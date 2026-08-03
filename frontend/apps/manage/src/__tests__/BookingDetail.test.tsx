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
const rescheduleBooking = vi.mocked(api.rescheduleBooking);
const listManageSlots = vi.mocked(api.listManageSlots);

function slot(startsAt: string, remaining = 2) {
  return { starts_at: startsAt, capacity: 3, remaining };
}

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
    checked_in_at: null,
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
    payment_status: null,
    refund_due_agorot: null,
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
        checked_in_at: null,
        customer_name: "מיכל לוי",
        appointment_type_name: "מדידה ראשונה",
        dress_name: "שמלת אלמה",
        payment_status: null,
        refund_due_agorot: null,
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

    // phone, appointment date, appointment time, seat, terms version. NOT the
    // dress size — see the bare-bdi case below.
    for (const value of ["+972501234567", "4.8.2099", "10:00", "2", "3"]) {
      const node = screen.getAllByText(value)[0];
      expect(node.tagName).toBe("BDI");
      expect(node).toHaveAttribute("dir", "ltr");
    }
  });

  it('leaves free text in a BARE bdi — dir="ltr" on Hebrew is the worse defect', async () => {
    mount({ dress_size: "מידה 36" });
    await screen.findByText("הלקוחה");

    // `dress_size` is a snapshot of `dress_variants.size_label`: unbounded
    // owner-typed TEXT with no numeric constraint, so «מידה 36» or «S ארוך» is
    // ordinary. Under dir="ltr" the digits render left of the Hebrew. The
    // storefront already reads this field as owner-authored free text
    // (ManageBookingPage, BookPage), and a bare bdi still renders a plain "36"
    // LTR — dir=auto has no strong character to disagree with.
    for (const value of ["מיכל לוי", "שמלת אלמה", "מידה 36", "באה עם אמא ואחות, מגיעות מחיפה"]) {
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

  it("hides the arrival fact on a booking nobody has checked in", async () => {
    mount();
    await screen.findByText("הלקוחה");
    expect(screen.queryByText("נרשמה הגעה")).toBeNull();
  });

  it("states the arrival as a FACT, and offers no control for it", async () => {
    // The action lives on the board, one place; the detail states the fact.
    // 06:24Z is 09:24 in Jerusalem, and the runner's TZ is New York.
    mount({ checked_in_at: "2099-08-04T06:24:00Z" });
    await screen.findByText("הלקוחה");

    expect(screen.getByText("נרשמה הגעה")).toBeInTheDocument();
    expect(screen.getByText("09:24")).toBeInTheDocument();
    // No «הגיעה» and no «ביטול הרישום» here — any change to the control's
    // placement in F15's detail screen is out of F34's scope.
    expect(screen.queryByRole("button", { name: /^הגיעה/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /ביטול הרישום/ })).toBeNull();
  });

  it("reads a checked-in no_show as two true facts rather than a contradiction", async () => {
    // D5: a status transition never touches checked_in_at, so this row is real.
    mount({ status: "no_show", checked_in_at: "2099-08-04T06:24:00Z" });
    await screen.findByText("הלקוחה");

    expect(screen.getByTestId("booking-status")).toHaveTextContent("לא הגיעה");
    expect(screen.getByText("נרשמה הגעה")).toBeInTheDocument();
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

  it("never strands focus on <body> — a plain action that fails moves it to the alert", async () => {
    // `disabled={busy}` blurs the button the instant it is tapped, and only the
    // SUCCESS path rescues focus (the cue effect). On failure nothing did: the
    // owner's next Tab restarted at the skip link and a screen-reader cursor
    // had left the panel. WCAG 2.4.3.
    mount({ status: "confirmed", starts_at: PAST });
    noShowBooking.mockRejectedValue(
      new ApiError(409, "BOOKING_TRANSITION_INVALID", "Not allowed."),
    );

    fireEvent.click(await screen.findByRole("button", { name: "סימון: לא הגיעה" }));

    const alert = await screen.findByRole("alert");
    await waitFor(() => expect(alert).toHaveFocus());
  });

  it("never strands focus after the cancel Modal's confirm fails", async () => {
    // The worst instance: `setConfirmingCancel(false)` and `setPending("cancel")`
    // batch into ONE commit, so the <dialog> unmounts (focus → <body>) while the
    // trigger it would be restored to is `disabled` in that same commit. The
    // restore effect's .focus() on a disabled button is a no-op.
    mount();
    cancelBooking.mockRejectedValue(
      new ApiError(409, "BOOKING_TRANSITION_INVALID", "Already started."),
    );

    fireEvent.click(await screen.findByRole("button", { name: "ביטול התור" }));
    fireEvent.click(
      within(dialogOf("לבטל את התור?")).getByRole("button", { name: "אישור הביטול" }),
    );

    const alert = await screen.findByRole("alert");
    await waitFor(() => expect(alert).toHaveFocus());
    expect(document.body).not.toHaveFocus();
  });

  it("moves focus to the phone field when the server rejects the number", async () => {
    // The 400 renders in the Input's own error slot, not the shared alert, so
    // focusing the alert would leave this path stranded.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "תיקון מספר הטלפון" }));
    fireEvent.change(screen.getByLabelText("מספר טלפון חדש"), { target: { value: "123" } });
    correctBookingPhone.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "phone: not an Israeli mobile"),
    );
    fireEvent.click(screen.getByRole("button", { name: "שמירת המספר" }));
    fireEvent.click(
      within(dialogOf("לעדכן את מספר הטלפון?")).getByRole("button", { name: "עדכון המספר" }),
    );

    await screen.findByText("phone: not an Israeli mobile");
    await waitFor(() => expect(screen.getByLabelText("מספר טלפון חדש")).toHaveFocus());
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

describe("RescheduleDialog", () => {
  // The booking sits at 10:00 Jerusalem on 2099-08-04, so the dialog's window
  // is that date through +13 days.
  const OPEN_DATE = "2099-08-04";
  const WINDOW_END = "2099-08-17";
  const NEXT = "2099-08-04T08:30:00Z"; // 11:30 Jerusalem, same day
  const FAR = "2099-08-25T07:00:00Z"; // outside the fetched window

  async function openDialog(slots = [slot(NEXT)]) {
    mount();
    listManageSlots.mockResolvedValue({ slots });
    fireEvent.click(await screen.findByRole("button", { name: "שינוי מועד" }));
    return dialogOf("שינוי מועד התור");
  }

  it("RD-load — a Skeleton in the body and a disabled confirm", async () => {
    mount();
    listManageSlots.mockReturnValue(new Promise(() => {}));
    fireEvent.click(await screen.findByRole("button", { name: "שינוי מועד" }));

    const dialog = dialogOf("שינוי מועד התור");
    expect(within(dialog).queryByRole("radiogroup")).toBeNull();
    expect(within(dialog).getByRole("button", { name: "עדכון המועד" })).toBeDisabled();
    expect(listManageSlots).toHaveBeenCalledWith(OPEN_DATE, WINDOW_END);
  });

  it("IS the confirm — one dialog, the consequence directly above the single submit", async () => {
    const dialog = await openDialog();
    await within(dialog).findByRole("radio", { name: "11:30" });

    expect(dialog).toHaveTextContent("המועד יתעדכן, והקישור של הלקוחה יצביע על המועד החדש.");
    // No second Modal stacked on this one: a focus trap over a focus trap for a
    // decision she is already reading.
    expect(document.querySelectorAll("dialog")).toHaveLength(1);
    expect(within(dialog).getAllByRole("button", { name: "עדכון המועד" })).toHaveLength(1);
  });

  it("RD — the booking's own time is present and pre-selected even when the grid drops it", async () => {
    // A capacity-1 target the booking itself occupies never comes back from the
    // engine, so the dialog injects it (D6).
    const dialog = await openDialog([slot(NEXT)]);
    const current = await within(dialog).findByRole("radio", { name: "10:00" });

    expect(current).toBeChecked();
    expect(within(dialog).getByRole("radio", { name: "11:30" })).not.toBeChecked();
    // The injected option carries the BARE time: SlotPicker renders every label
    // inside <bdi dir="ltr">, so appending Hebrew would be a bidi defect.
    expect(current.closest("label")?.textContent).toBe("10:00");
    // It is named above the picker instead.
    expect(dialog).toHaveTextContent("המועד הנוכחי:");
    expect(dialog).toHaveTextContent("4.8.2099");
  });

  it("does not duplicate the current time when the grid already carries it", async () => {
    const dialog = await openDialog([slot(FUTURE), slot(NEXT)]);
    await within(dialog).findByRole("radio", { name: "11:30" });

    expect(within(dialog).getAllByRole("radio", { name: "10:00" })).toHaveLength(1);
  });

  it("RD-empty — SlotPicker's own no-slots block, and no second empty message", async () => {
    // Another date in the window with nothing on it.
    const dialog = await openDialog([]);
    fireEvent.change(await within(dialog).findByLabelText("תאריך"), {
      target: { value: "2099-08-06" },
    });

    expect(
      within(dialog).getByText(
        "אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, או לפתוח שעות נוספות במסך «שעות פעילות».",
      ),
    ).toBeInTheDocument();
    // Two stacked empty messages for one emptiness would be worse (design P-4).
    expect(within(dialog).queryByText("אין תורים בתאריך הזה")).toBeNull();
    expect(within(dialog).getByRole("button", { name: "עדכון המועד" })).toBeDisabled();
  });

  it("refetches only when the chosen date leaves the fetched window", async () => {
    const dialog = await openDialog();
    await within(dialog).findByRole("radio", { name: "11:30" });
    const field = within(dialog).getByLabelText("תאריך");
    expect(listManageSlots).toHaveBeenCalledTimes(1);

    // Inside the 14-day window: filtered in memory, no round trip.
    fireEvent.change(field, { target: { value: "2099-08-10" } });
    expect(listManageSlots).toHaveBeenCalledTimes(1);

    // Outside it: a fresh window anchored at the new date.
    fireEvent.change(field, { target: { value: "2099-09-02" } });
    await waitFor(() =>
      expect(listManageSlots).toHaveBeenLastCalledWith("2099-09-02", "2099-09-15"),
    );
  });

  it("bounds the picker below at today and NOT above — the horizon is a server bound", async () => {
    const dialog = await openDialog();
    const field = await within(dialog).findByLabelText("תאריך");

    expect(field).toHaveAttribute("min");
    // F15 mirrors no server bound client-side: a date past the horizon simply
    // materializes no slots, which is the truth.
    expect(field).not.toHaveAttribute("max");
  });

  it("RD-fail — a 409 keeps the dialog OPEN with the grid intact", async () => {
    const dialog = await openDialog();
    fireEvent.click(await within(dialog).findByRole("radio", { name: "11:30" }));

    rescheduleBooking.mockRejectedValue(
      new ApiError(409, "SLOT_UNAVAILABLE", "That time was just taken. Choose another."),
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "עדכון המועד" }));

    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("המועד הזה נתפס הרגע. אפשר לבחור מועד אחר.");
    expect(alert).toHaveClass("text-danger");
    // Closing it would throw away the fetch she needs to pick again.
    expect(dialogOf("שינוי מועד התור")).toBeInTheDocument();
    expect(within(dialog).getByRole("radio", { name: "11:30" })).toBeInTheDocument();
    expect(listManageSlots).toHaveBeenCalledTimes(1);
  });

  it("disables the submit while the request is in flight", async () => {
    const dialog = await openDialog();
    fireEvent.click(await within(dialog).findByRole("radio", { name: "11:30" }));

    rescheduleBooking.mockReturnValue(new Promise(() => {}));
    fireEvent.click(within(dialog).getByRole("button", { name: "עדכון המועד" }));

    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: "עדכון המועד" })).toBeDisabled(),
    );
    expect(rescheduleBooking).toHaveBeenCalledTimes(1);
  });

  it("closes on success, re-renders the detail from the response and announces it", async () => {
    const dialog = await openDialog();
    fireEvent.click(await within(dialog).findByRole("radio", { name: "11:30" }));

    rescheduleBooking.mockResolvedValue(detail({ starts_at: NEXT }));
    fireEvent.click(within(dialog).getByRole("button", { name: "עדכון המועד" }));

    expect(await screen.findByText("המועד עודכן.")).toBeInTheDocument();
    expect(document.querySelectorAll("dialog")).toHaveLength(0);
    // The whole detail re-renders from the response, never from what the client
    // hoped: the facts now read 11:30.
    expect(screen.getByText("11:30")).toBeInTheDocument();
    expect(rescheduleBooking).toHaveBeenCalledWith("b1", NEXT);
  });

  it("restores focus to the trigger when the dialog is dismissed", async () => {
    mount();
    listManageSlots.mockResolvedValue({ slots: [slot(NEXT)] });
    const trigger = await screen.findByRole("button", { name: "שינוי מועד" });
    fireEvent.click(trigger);

    fireEvent.click(
      within(dialogOf("שינוי מועד התור")).getByRole("button", { name: "חזרה" }),
    );

    await waitFor(() => expect(trigger).toHaveFocus());
    expect(rescheduleBooking).not.toHaveBeenCalled();
  });

  it("refetches the day after a move — a patched row cannot keep the list truthful", async () => {
    // `starts_at` is the one field list MEMBERSHIP, the server `total` and the
    // server's (starts_at, seat_index) ORDER are all derived from. Patching the
    // object in place leaves the row parked at its old index; the same-day move
    // below is the mild case, the cross-day one under it is the dangerous one.
    listBookings.mockResolvedValue(listRow());
    getBooking.mockResolvedValue(detail());
    listManageSlots.mockResolvedValue({ slots: [slot(NEXT)] });
    rescheduleBooking.mockResolvedValue(detail({ starts_at: NEXT }));

    render(<BookingsSection />);
    fireEvent.click(await screen.findByRole("button", { name: /מיכל לוי/ }));
    await screen.findByText("הלקוחה");
    fireEvent.click(screen.getByRole("button", { name: "שינוי מועד" }));

    const dialog = dialogOf("שינוי מועד התור");
    fireEvent.click(await within(dialog).findByRole("radio", { name: "11:30" }));
    listBookings.mockResolvedValue(listRow({ starts_at: NEXT }));
    fireEvent.click(within(dialog).getByRole("button", { name: "עדכון המועד" }));
    await screen.findByText("המועד עודכן.");

    await waitFor(() => expect(listBookings).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));
    expect(await screen.findByText("11:30")).toBeInTheDocument();
  });

  it("drops the row from the filtered day when the move leaves it", async () => {
    // The list deliberately prints no date (the date IS the filter), so a row
    // left behind by a cross-day move is visually indistinguishable from a real
    // one — the owner reads 09:00 on the 4th and prepares for an appointment
    // that is on the 6th. The announced count would stay wrong too.
    const OTHER_DAY = "2099-08-06T06:00:00Z"; // 09:00 Jerusalem, two days on
    listBookings.mockResolvedValue(listRow());
    getBooking.mockResolvedValue(detail());
    listManageSlots.mockResolvedValue({ slots: [slot(NEXT), slot(OTHER_DAY)] });
    rescheduleBooking.mockResolvedValue(detail({ starts_at: OTHER_DAY }));

    render(<BookingsSection />);
    fireEvent.click(await screen.findByRole("button", { name: /מיכל לוי/ }));
    await screen.findByText("הלקוחה");
    fireEvent.click(screen.getByRole("button", { name: "שינוי מועד" }));

    const dialog = dialogOf("שינוי מועד התור");
    fireEvent.change(await within(dialog).findByLabelText("תאריך"), {
      target: { value: "2099-08-06" },
    });
    fireEvent.click(await within(dialog).findByRole("radio", { name: "09:00" }));

    // The 4th, refetched, no longer holds it.
    listBookings.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 50 });
    fireEvent.click(within(dialog).getByRole("button", { name: "עדכון המועד" }));
    await screen.findByText("המועד עודכן.");

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));

    expect(await screen.findByText("אין תורים בתאריך הזה")).toBeInTheDocument();
    expect(screen.getByTestId("bookings-count")).toHaveTextContent("תורים ביום זה: 0");
    // Same day as the first call — the FILTER did not change, the booking left
    // it. Only the refetch can know that.
    expect(listBookings).toHaveBeenCalledTimes(2);
    expect(listBookings.mock.calls[1]).toEqual(listBookings.mock.calls[0]);
  });

  it("announces nothing when the pre-selected time is re-submitted unchanged", async () => {
    // The current time is always present and pre-selected (D6), so the confirm
    // is live the moment the grid loads and this is one tap away. The server
    // short-circuits to a no-op 200: no audit row, no send, nothing changed —
    // and «המועד עודכן» would state a state change that did not happen.
    const dialog = await openDialog();
    await within(dialog).findByRole("radio", { name: "11:30" });

    rescheduleBooking.mockResolvedValue(detail());
    fireEvent.click(within(dialog).getByRole("button", { name: "עדכון המועד" }));

    await waitFor(() => expect(document.querySelectorAll("dialog")).toHaveLength(0));
    expect(screen.getByTestId("booking-cue")).toHaveTextContent("");
  });

  it("surfaces a slot-fetch failure in the OUTAGE register without closing", async () => {
    mount();
    listManageSlots.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "Down."));
    fireEvent.click(await screen.findByRole("button", { name: "שינוי מועד" }));

    const dialog = dialogOf("שינוי מועד התור");
    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveClass("text-ink-muted");
    expect(within(dialog).getByRole("button", { name: "עדכון המועד" })).toBeDisabled();
  });

  it("offers a retry, because the branch it replaces owns the only refetch control", async () => {
    // The list's L-fail declines a retry control on the grounds that
    // re-selecting the date refetches — true there, because its DateField sits
    // in a Card ABOVE the alert. Here the alert REPLACES SlotPicker, and the
    // DateField lives inside it, so the dialog is left with one disabled
    // control and «חזרה». The storefront's own slots outage ships this button.
    mount();
    listManageSlots.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "Down."));
    fireEvent.click(await screen.findByRole("button", { name: "שינוי מועד" }));

    const dialog = dialogOf("שינוי מועד התור");
    await within(dialog).findByRole("alert");
    expect(listManageSlots).toHaveBeenCalledTimes(1);

    listManageSlots.mockResolvedValue({ slots: [slot(NEXT)] });
    fireEvent.click(within(dialog).getByRole("button", { name: "ניסיון נוסף" }));

    expect(await within(dialog).findByRole("radio", { name: "11:30" })).toBeInTheDocument();
    expect(listManageSlots).toHaveBeenCalledTimes(2);
    expect(within(dialog).queryByRole("alert")).toBeNull();
  });

  it("passes axe with zero violations with the dialog open", async () => {
    getBooking.mockResolvedValue(detail());
    listManageSlots.mockResolvedValue({ slots: [slot(NEXT), slot(FAR)] });
    const { container } = renderInShell(
      <BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "שינוי מועד" }));
    await within(dialogOf("שינוי מועד התור")).findByRole("radio", { name: "11:30" });

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);
});

describe("BookingDetail — the fifth status (F19 D14)", () => {
  const RESCHEDULE = "שינוי מועד";
  const RESEND = "הנפקת קישור ניהול חדש";
  const PHONE = "תיקון מספר הטלפון";
  const CANCEL = "ביטול התור";
  const NO_SHOW = "סימון: לא הגיעה";
  const COMPLETE = "סימון: התקיים";
  const REOPEN = "החזרה לסטטוס מאושר";
  const RESTORE = "קביעת מועד חדש ושחזור התור";
  const ALL = [RESCHEDULE, RESEND, PHONE, CANCEL, NO_SHOW, COMPLETE, REOPEN, RESTORE];

  async function controlsFor(overrides: Partial<OwnerBookingDetail>) {
    mount(overrides);
    await screen.findByText("הלקוחה");
    return ALL.filter((name) => screen.queryByRole("button", { name }) !== null);
  }

  it("renders a real Hebrew badge, never the raw LTR wire value", async () => {
    mount({ status: "pending_payment", payment_status: "pending" });
    await screen.findByText("הלקוחה");

    expect(screen.getByTestId("booking-status")).toHaveTextContent("ממתין לתשלום");
    expect(screen.getByTestId("booking-status")).not.toHaveTextContent("pending_payment");
  });

  it("is the SIXTH branch — a state, and no owner actions at all", async () => {
    // Before this branch a pending_payment booking satisfied none of the five
    // booleans, so the panel rendered with no state and no action set. Every
    // owner verb 409s on an unpaid hold, so none is offered.
    expect(await controlsFor({ status: "pending_payment", starts_at: FUTURE })).toEqual([]);
    expect(
      screen.getByText(
        "התור ממתין לתשלום הפיקדון. עד להשלמת התשלום אין פעולות זמינות, ואם התשלום לא יושלם המועד יתפנה מעצמו.",
      ),
    ).toBeInTheDocument();
    // Nothing will be sent from here, so the standing delivery limit is not
    // stated either — same rule the cancelled branch follows.
    expect(screen.queryByText(/אין באפשרותנו לאמת/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("BookingDetail payment surface (F19 D18 / A1)", () => {
  it("renders payment_status as its own badge, distinct from the status chip", async () => {
    mount({ status: "confirmed", payment_status: "paid" });
    await screen.findByText("הלקוחה");

    expect(screen.getByText("תשלום")).toBeInTheDocument();
    expect(screen.getByTestId("booking-payment")).toHaveTextContent("שולם");
    expect(screen.getByTestId("booking-status")).toHaveTextContent("מאושר");
  });

  it("shows nothing at all when no payment row exists", async () => {
    mount({ payment_status: null, refund_due_agorot: null });
    await screen.findByText("הלקוחה");

    expect(screen.queryByTestId("booking-payment")).toBeNull();
    expect(screen.queryByTestId("booking-payment-action")).toBeNull();
    expect(screen.queryByText("סכום להחזר")).toBeNull();
  });

  it("marks the first action-needed case — cancelled, and the deposit still held", async () => {
    mount({ status: "cancelled", payment_status: "paid", cancelled_at: PAST });
    await screen.findByText("הלקוחה");

    const marker = screen.getByTestId("booking-payment-action");
    expect(marker).toHaveTextContent("דרושה פעולה: התור בוטל והפיקדון עדיין מוחזק בבוטיק.");
    // The Hebrew opens with «דרושה פעולה», so the marker never depends on colour.
    expect(marker.textContent?.startsWith("דרושה פעולה")).toBe(true);
  });

  it("marks the second — MD4's confirmed booking that took no deposit", async () => {
    mount({ status: "confirmed", payment_status: "failed" });
    await screen.findByText("הלקוחה");

    expect(screen.getByTestId("booking-payment-action")).toHaveTextContent(
      "דרושה פעולה: התור נקבע ללא פיקדון, משום שספק הסליקה לא היה זמין בעת ההזמנה.",
    );
    expect(screen.getByTestId("booking-payment")).toHaveTextContent("נכשל");
  });

  it("stays quiet on an ordinary paid booking and an ordinary expired hold", async () => {
    mount({ status: "confirmed", payment_status: "paid" });
    await screen.findByText("הלקוחה");
    expect(screen.queryByTestId("booking-payment-action")).toBeNull();
    cleanup();

    vi.clearAllMocks();
    mount({ status: "cancelled", payment_status: "expired" });
    await screen.findByText("הלקוחה");
    expect(screen.queryByTestId("booking-payment-action")).toBeNull();
  });

  it("renders refund_due_agorot through <Price> — agorot are integers to the render", async () => {
    // D15: 25000 agorot is ₪250, divided by 100 exactly once, inside the shared
    // component, in an LTR-isolated run.
    mount({ status: "cancelled", payment_status: "paid", refund_due_agorot: 25000 });
    await screen.findByText("הלקוחה");

    expect(screen.getByText("סכום להחזר")).toBeInTheDocument();
    const amount = screen.getByText("250 ₪");
    expect(amount.tagName).toBe("BDI");
    expect(amount).toHaveAttribute("dir", "ltr");
    // The raw agorot never reach the page.
    expect(screen.queryByText(/25000/)).toBeNull();
  });

  it("renders a zero refund as ₪0 rather than hiding the row", async () => {
    // Outside the window the whole deposit is forfeit; that is a fact the owner
    // needs, and a hidden row reads as "not computed".
    mount({ status: "cancelled", payment_status: "paid", refund_due_agorot: 0 });
    await screen.findByText("הלקוחה");
    expect(screen.getByText("0 ₪")).toBeInTheDocument();
  });
});

describe("BookingDetail — MD1's reschedule on a cancelled, paid booking", () => {
  const RESTORE = "קביעת מועד חדש ושחזור התור";

  it("offers the action, and replaces the sentence that would contradict it", async () => {
    mount({ status: "cancelled", payment_status: "paid", cancelled_at: PAST });
    await screen.findByText("פעולות");

    expect(screen.getByRole("button", { name: RESTORE })).toBeInTheDocument();
    expect(
      screen.getByText(
        "התור בוטל והפיקדון עדיין מוחזק בבוטיק. אפשר לקבוע ללקוחה מועד חדש, והתור יחזור לסטטוס מאושר.",
      ),
    ).toBeInTheDocument();
    // The shipped sentence becomes FALSE on exactly this row the day MD1 merges,
    // and would otherwise render directly above the button that disproves it.
    expect(screen.queryByText(/תור שבוטל אינו ניתן לשחזור/)).toBeNull();
    // An action exists here, so the standing delivery limit is stated.
    expect(screen.getByText(/אין באפשרותנו לאמת/)).toBeInTheDocument();
  });

  it("is ABSENT on a cancelled booking with no deposit held", async () => {
    mount({ status: "cancelled", payment_status: null, cancelled_at: PAST });
    await screen.findByText("פעולות");

    expect(screen.queryByRole("button", { name: RESTORE })).toBeNull();
    expect(screen.getByText(/תור שבוטל אינו ניתן לשחזור/)).toBeInTheDocument();
  });

  it("is ABSENT when the deposit expired or failed rather than landing", async () => {
    for (const payment of ["expired", "failed", "pending"]) {
      vi.clearAllMocks();
      mount({ status: "cancelled", payment_status: payment, cancelled_at: PAST });
      await screen.findByText("פעולות");
      expect(screen.queryByRole("button", { name: RESTORE })).toBeNull();
      cleanup();
    }
  });

  it("opens the reschedule dialog — the button behind D18's marker is live", async () => {
    mount({ status: "cancelled", payment_status: "paid", cancelled_at: PAST });
    listManageSlots.mockResolvedValue({ slots: [slot("2099-08-04T08:30:00Z")] });

    fireEvent.click(await screen.findByRole("button", { name: RESTORE }));

    expect(dialogOf("שינוי מועד התור")).toBeInTheDocument();
  });

  it("announces the un-cancel even when the time did not move, and keeps focus", async () => {
    // The starts_at comparison alone cannot see this: MD1's widened UPDATE also
    // restores the status, and a restore at the SAME time is a real change. The
    // branch rendering the trigger unmounts with it, so a missing cue would also
    // strand focus on <body> (WCAG 2.4.3).
    mount({ status: "cancelled", payment_status: "paid", cancelled_at: PAST });
    listManageSlots.mockResolvedValue({ slots: [] });
    fireEvent.click(await screen.findByRole("button", { name: RESTORE }));

    const dialog = dialogOf("שינוי מועד התור");
    rescheduleBooking.mockResolvedValue(
      detail({ status: "confirmed", payment_status: "paid", cancelled_at: null }),
    );
    fireEvent.click(await within(dialog).findByRole("button", { name: "עדכון המועד" }));

    expect(await screen.findByText("התור הוחזר לסטטוס מאושר במועד שנבחר.")).toBeInTheDocument();
    // …and not the time-moved sentence, which did not happen.
    expect(screen.queryByText("המועד עודכן.")).toBeNull();
    // Focus never drops to <body>: the restore trigger unmounts, and the shared
    // ref follows the live booking's own reschedule control into the branch that
    // replaces it. The cue is announced by role="status" either way.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "שינוי מועד" })).toHaveFocus(),
    );
    expect(document.body).not.toHaveFocus();
    // The row is no longer an anomaly, so the marker and its button are gone.
    expect(screen.queryByTestId("booking-payment-action")).toBeNull();
    expect(screen.queryByRole("button", { name: RESTORE })).toBeNull();
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

  it("passes axe with the payment badge, the marker and the refund all rendered", async () => {
    // The one screen that carries every F19 addition at once: a second Badge, a
    // text-danger marker and a <Price> run, inside an RTL panel.
    getBooking.mockResolvedValue(
      detail({
        status: "cancelled",
        payment_status: "paid",
        refund_due_agorot: 25000,
        cancelled_at: "2099-08-02T09:00:00Z",
        cancelled_by: "customer",
      }),
    );
    const { container } = renderInShell(
      <BookingDetail bookingId="b1" onBack={vi.fn()} onBookingChanged={vi.fn()} />,
    );
    await screen.findByRole("heading", { name: "הפגישה" });

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
