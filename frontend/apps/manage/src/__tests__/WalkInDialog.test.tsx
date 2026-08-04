import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { AppointmentType, CustomerRow } from "../api";
import { WalkInDialog } from "../components/WalkInDialog";

/**
 * F50's only new component.
 *
 * ⚠ WHAT IS DELIBERATELY NOT ASSERTED HERE: focus placement on open, the focus
 * TRAP, Esc, and the focus return to «תור חדש». `test/setup.ts` stubs
 * `HTMLDialogElement.showModal()` as `this.open = true` and nothing else — no
 * focus move, no trap, no top layer, no `cancel` on Esc — so every one of those
 * assertions would measure the stub and CANNOT FAIL. They live in
 * `frontend/e2e/dialog-focus.spec.ts`, which runs in a browser that implements
 * <dialog> and carries a mutation ledger. Everything below is about STATE, which
 * jsdom reports honestly.
 */

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      listCustomers: vi.fn(),
      listAppointmentTypes: vi.fn(),
    },
  };
});

const { api } = await import("../api");
const listCustomers = vi.mocked(api.listCustomers);
const listAppointmentTypes = vi.mocked(api.listAppointmentTypes);

const DEBOUNCE = 300;

const MICHAL: CustomerRow = {
  id: "c-michal",
  name: "מיכל לוי",
  phone: "+972501234567",
  tags: [],
};
const NOA: CustomerRow = { id: "c-noa", name: "נועה כהן", phone: "+972529876543", tags: [] };

const FITTING: AppointmentType = {
  id: "at-1",
  name: "מדידה ראשונה",
  duration_minutes: 60,
  audience: "brides_only",
  deposit_required: false,
  deposit_amount_agorot: null,
  sort_order: 1,
};

function page(items: CustomerRow[], total = items.length) {
  return { items, total, offset: 0, limit: 10 };
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function flush() {
  await advance(0);
}

async function type(value: string) {
  const box = screen.getByLabelText("לקוחה");
  await act(async () => {
    fireEvent.change(box, { target: { value } });
    await vi.advanceTimersByTimeAsync(0);
  });
}

async function click(element: HTMLElement) {
  await act(async () => {
    fireEvent.click(element);
    await vi.advanceTimersByTimeAsync(0);
  });
}

function confirmButton() {
  return screen.getByRole("button", { name: "יצירת התור" });
}

async function mount(onConfirm = vi.fn().mockResolvedValue(null)) {
  const onClose = vi.fn();
  const view = render(<WalkInDialog open onClose={onClose} onConfirm={onConfirm} />);
  await flush();
  return { ...view, onClose, onConfirm };
}

// Search, pick a customer, pick a type — the state the confirm needs.
async function pickBoth() {
  await type("מיכל");
  await advance(DEBOUNCE);
  await click(screen.getByRole("radio", { name: /מיכל לוי/ }));
  await act(async () => {
    fireEvent.change(screen.getByLabelText("סוג הפגישה"), { target: { value: "at-1" } });
    await vi.advanceTimersByTimeAsync(0);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  listAppointmentTypes.mockResolvedValue([FITTING]);
  listCustomers.mockResolvedValue(page([MICHAL]));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("WalkInDialog search", () => {
  it("issues NO search for a blank box, and no result list either", async () => {
    await mount();
    await advance(DEBOUNCE * 3);

    // A blank box is not a search: the server would answer «everyone», which is
    // a page of names nobody asked for.
    expect(listCustomers).not.toHaveBeenCalled();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByTestId("walkin-empty")).toBeNull();
  });

  it("debounces to ONE request per pause, not one per keystroke", async () => {
    await mount();

    await type("מ");
    await type("מי");
    await type("מיכ");
    await advance(DEBOUNCE - 1);
    // ⚠ The assertion that makes this a debounce test rather than a search
    // test: nothing has been sent yet, three keystrokes in.
    expect(listCustomers).not.toHaveBeenCalled();

    await advance(1);
    expect(listCustomers).toHaveBeenCalledTimes(1);
    expect(listCustomers).toHaveBeenCalledWith({ q: "מיכ", offset: 0, limit: 10 });
  });

  it("renders each result as a radio carrying the name AND the phone", async () => {
    listCustomers.mockResolvedValue(page([MICHAL, NOA]));
    await mount();
    await type("לוי");
    await advance(DEBOUNCE);

    const group = screen.getByRole("group", { name: "בחירת הלקוחה" });
    expect(within(group).getAllByRole("radio")).toHaveLength(2);
    // The phone is the disambiguator two brides with one name need, which is
    // why CustomerRow ships it at all.
    expect(within(group).getByRole("radio", { name: /\+972501234567/ })).toBeInTheDocument();
    // A Hebrew name in a BARE bdi: dir="ltr" would reverse its words.
    const name = within(group).getByText("מיכל לוי");
    expect(name.tagName).toBe("BDI");
    expect(name).not.toHaveAttribute("dir");
    // The phone IS forced LTR — it is a numeric run.
    expect(within(group).getByText("+972501234567")).toHaveAttribute("dir", "ltr");
  });

  it("says so when the ten shown are not all of them", async () => {
    listCustomers.mockResolvedValue(page([MICHAL, NOA], 40));
    await mount();
    await type("לוי");
    await advance(DEBOUNCE);

    expect(screen.getByText(/מוצגות 2 הלקוחות הראשונות/)).toBeInTheDocument();
  });

  it("drops a customer already chosen when the term changes", async () => {
    await mount();
    await pickBoth();
    expect(confirmButton()).toBeEnabled();

    listCustomers.mockResolvedValue(page([NOA]));
    await type("נועה");
    await advance(DEBOUNCE);

    // A customer chosen out of the previous result set is not a customer in
    // this one — and the confirm must not stay armed pointing at her.
    expect(screen.getByRole("radio", { name: /נועה כהן/ })).not.toBeChecked();
    expect(confirmButton()).toBeDisabled();
  });

  it("shows an alert when the search itself fails", async () => {
    listCustomers.mockRejectedValue(new Error("network"));
    await mount();
    await type("מיכל");
    await advance(DEBOUNCE);

    expect(screen.getByRole("alert")).toHaveTextContent("לא הצלחנו לחפש לקוחות כרגע.");
    // NOT the empty state: «nobody matched» and «we could not ask» are different
    // answers and must not render the same.
    expect(screen.queryByTestId("walkin-empty")).toBeNull();
  });
});

describe("WalkInDialog empty state — D3's ruling as copy", () => {
  it("routes a search that matched nobody to the check-in form, and offers no way to add her", async () => {
    // ⚠ THE LOAD-BEARING TEST OF THIS COMPONENT. A walk-in for a customer the
    // boutique does not yet hold is refused ON PURPOSE: a `customers` row is
    // proof of phone possession because it is written only after an OTP, and a
    // dialog that typed a name and a number would be a fourth §11 collection
    // point whose notice could only be delivered by asking a staffer to recite
    // it. The empty state is where that ruling meets the staffer, so it is
    // asserted rather than left to the copy deck.
    listCustomers.mockResolvedValue(page([]));
    await mount();
    await type("שם שלא קיים");
    await advance(DEBOUNCE);

    const empty = screen.getByTestId("walkin-empty");
    expect(empty).toHaveTextContent("לא נמצאה לקוחה עם השם או הטלפון האלה.");
    // It names the screen that prints the code, by the nav label that screen
    // actually carries.
    expect(empty).toHaveTextContent("קוד סריקה");
    // Not an error and not announced: this is the ordinary answer to a search.
    expect(empty).not.toHaveAttribute("role", "alert");
    expect(screen.queryByRole("alert")).toBeNull();
    // And there is no create-a-customer affordance anywhere in the dialog.
    expect(screen.queryByRole("button", { name: /הוספת|לקוחה חדשה/ })).toBeNull();
  });
});

describe("WalkInDialog appointment type", () => {
  it("fetches the types ONCE on open and lists them", async () => {
    await mount();
    await type("מיכל");
    await advance(DEBOUNCE * 3);

    expect(listAppointmentTypes).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("option", { name: "מדידה ראשונה" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "בחירת סוג פגישה" })).toBeInTheDocument();
  });

  it("says so when the boutique has configured none, and names where to", async () => {
    listAppointmentTypes.mockResolvedValue([]);
    await mount();

    expect(screen.getByText(/לא הוגדרו סוגי פגישות/)).toHaveTextContent("סוגי תורים");
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(confirmButton()).toBeDisabled();
  });

  it("shows an alert when the type list fails to load", async () => {
    listAppointmentTypes.mockRejectedValue(new Error("network"));
    await mount();

    expect(screen.getByRole("alert")).toHaveTextContent("לא הצלחנו לטעון את סוגי הפגישות כרגע.");
  });
});

describe("WalkInDialog confirm", () => {
  it("stays disabled until BOTH a customer and a type are chosen", async () => {
    await mount();
    expect(confirmButton()).toBeDisabled();

    await type("מיכל");
    await advance(DEBOUNCE);
    await click(screen.getByRole("radio", { name: /מיכל לוי/ }));
    // A customer alone is not enough.
    expect(confirmButton()).toBeDisabled();

    await act(async () => {
      fireEvent.change(screen.getByLabelText("סוג הפגישה"), { target: { value: "at-1" } });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(confirmButton()).toBeEnabled();
  });

  it("sends EXACTLY two keys, and they are the two ids", async () => {
    // ⚠ Object.keys equality, not a `toMatchObject`. Every absence in this body
    // is a ruling: no name and no phone (nothing is obtained from the subject,
    // so no §11 notice is owed), no `marketing_consent` (an absent field is the
    // only spelling a future caller cannot flip), no `starts_at` (the instant is
    // the server's `now`, which is what keeps the row outside four shipped
    // writers). A later `notes` added «for convenience» reds here.
    const { onConfirm } = await mount();
    await pickBoth();
    await click(confirmButton());

    expect(onConfirm).toHaveBeenCalledTimes(1);
    const body = onConfirm.mock.calls[0][0] as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["appointment_type_id", "customer_id"]);
    expect(body).toEqual({ customer_id: "c-michal", appointment_type_id: "at-1" });
  });

  it("renders the parent's error sentence and STAYS OPEN", async () => {
    // The parent owns bookingErrorText and the {401,403} classifier; this
    // component renders whatever sentence comes back. Closing on a failure would
    // throw away the search she would have to run again.
    const onConfirm = vi.fn().mockResolvedValue("המועד הזה נתפס הרגע. אפשר לבחור מועד אחר.");
    const { onClose } = await mount(onConfirm);
    await pickBoth();
    await click(confirmButton());

    expect(screen.getByRole("alert")).toHaveTextContent("המועד הזה נתפס הרגע.");
    expect(onClose).not.toHaveBeenCalled();
    // Still armed: one tap retries, and the whole selection survives.
    expect(confirmButton()).toBeEnabled();
  });

  it("shows no error of its own when the parent answers null", async () => {
    // null = handled — a success the parent closed on, or a terminal that
    // replaced the whole board. Either way this dialog says nothing.
    const { onConfirm } = await mount();
    await pickBoth();
    await click(confirmButton());

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("WalkInDialog axe", () => {
  it("has zero A/AA violations with results and a type list on screen", async () => {
    // Real timers: axe schedules its own work on the macrotask queue and never
    // settles under a frozen clock. The debounce is waited out by the query
    // rather than advanced.
    vi.useRealTimers();
    listCustomers.mockResolvedValue(page([MICHAL, NOA]));
    const onConfirm = vi.fn().mockResolvedValue(null);
    const { container } = render(<WalkInDialog open onClose={vi.fn()} onConfirm={onConfirm} />);
    fireEvent.change(await screen.findByLabelText("לקוחה"), { target: { value: "לוי" } });
    await screen.findByRole("radio", { name: /מיכל לוי/ }, { timeout: 2000 });

    const results = await run(container, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  }, 20000);
});
