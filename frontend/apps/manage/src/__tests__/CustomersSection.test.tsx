import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { CustomerDetailResponse, CustomerListResponse, CustomerRow } from "../api";
import { CustomersSection } from "../components/CustomersSection";
import { MAX_SEARCH_TERM_LENGTH, MAX_TAG_LENGTH, MAX_TAGS } from "../validation";
import i18n from "../i18n";

// importActual re-exports the REAL ApiError and errorMessage so `instanceof`
// still works inside the components under test.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      listCustomers: vi.fn(),
      getCustomer: vi.fn(),
      updateCustomer: vi.fn(),
      withdrawMarketingConsent: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const listCustomers = vi.mocked(api.listCustomers);
const getCustomer = vi.mocked(api.getCustomer);
const updateCustomer = vi.mocked(api.updateCustomer);
const withdrawMarketingConsent = vi.mocked(api.withdrawMarketingConsent);

const CUSTOMER_ID = "33333333-4444-5555-6666-777777777777";

function row(overrides: Partial<CustomerRow> = {}): CustomerRow {
  return {
    id: CUSTOMER_ID,
    name: "מיכל לוי",
    phone: "+972501234567",
    tags: ["VIP", "כלה"],
    ...overrides,
  };
}

function page(items: CustomerRow[], total = items.length): CustomerListResponse {
  return { items, total, offset: 0, limit: 50 };
}

function detail(overrides: Partial<CustomerDetailResponse> = {}): CustomerDetailResponse {
  return {
    id: CUSTOMER_ID,
    name: "מיכל לוי",
    phone: "+972501234567",
    notes: "מעדיפה תור בבוקר",
    tags: ["VIP"],
    bookings: [
      {
        id: "b1",
        // 07:00Z is 10:00 in Jerusalem and 03:00 in New York, and this script
        // pins TZ=America/New_York — an unzoned read would print 03:00.
        starts_at: "2026-08-04T07:00:00Z",
        status: "confirmed",
        appointment_type_name: "מדידה ראשונה",
      },
    ],
    messages: [
      {
        id: "m1",
        created_at: "2026-08-03T05:30:00Z",
        kind: "confirmation",
        status: "sent",
        body: "התור שלך אושר",
      },
    ],
    messages_total: 1,
    // F20: no consent, never withdrawn, never erased — the state a brand-new
    // customer row is in, and the one the badge renders as «לא ניתנה».
    marketing_consent_at: null,
    marketing_consent_withdrawn_at: null,
    erased_at: null,
    ...overrides,
  };
}

// CustomersSection renders inside ConsoleShell's <main>, which owns the
// console's single sr-only <h1>. The axe harness reproduces that frame rather
// than scanning a headless fragment.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

async function openDetail() {
  renderInShell(<CustomersSection />);
  fireEvent.click(await screen.findByText("מיכל לוי"));
  return screen.findByRole("heading", { level: 3, name: "היסטוריית תורים" });
}

// Mirrors SEARCH_DEBOUNCE_MS, and CustomerDetail's BOOKING_HISTORY_LIMIT.
// Neither is exported and neither is parity-guarded — the component says why for
// the limit, and a drift in the debounce makes the wait below too short, which
// fails loudly rather than silently.
const SEARCH_DEBOUNCE_MS = 300;
const BOOKING_HISTORY_LIMIT = 50;

// EVERY refetch this component can make is scheduled inside
// setTimeout(…, SEARCH_DEBOUNCE_MS). So `toHaveBeenCalledTimes(1)` read on the
// microtask after an await that resolved synchronously is taken ~300ms BEFORE
// the refetch it is supposed to catch is even due, and asserts nothing at all:
// adding `selectedId` to the effect's dep array — two extra round trips for
// every card opened — left both call-count tests green and byte-identical.
// Letting the window elapse first is what makes them assertions.
async function afterTheDebounceWindow() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, SEARCH_DEBOUNCE_MS + 1));
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  listCustomers.mockResolvedValue(page([row()]));
  getCustomer.mockResolvedValue(detail());
});

afterEach(() => {
  vi.useRealTimers();
});

describe("CustomersSection list", () => {
  it("announces the loading state and shows a skeleton before the first page lands", () => {
    listCustomers.mockReturnValue(new Promise(() => {}));
    renderInShell(<CustomersSection />);
    expect(screen.getByTestId("customers-count")).toHaveTextContent("טוען את רשימת הלקוחות…");
  });

  it("announces the count once the page lands", async () => {
    listCustomers.mockResolvedValue(page([row()], 37));
    renderInShell(<CustomersSection />);
    await waitFor(() =>
      expect(screen.getByTestId("customers-count")).toHaveTextContent("לקוחות ברשימה: 37"),
    );
  });

  it("renders the name in a bare bdi and the phone in an ltr-isolated one", async () => {
    renderInShell(<CustomersSection />);
    const name = await screen.findByText("מיכל לוי");
    expect(name.tagName).toBe("BDI");
    // dir="ltr" on a Hebrew name is itself a bidi defect.
    expect(name).not.toHaveAttribute("dir");
    const phone = screen.getByText("+972501234567");
    expect(phone.tagName).toBe("BDI");
    expect(phone).toHaveAttribute("dir", "ltr");
  });

  // MAX_TAGS already bounds the set and the row wraps, so a "+N" token would be
  // user-visible text with no copy-deck key AND a digit run beside a `+`
  // between Hebrew chips — the exact bidi hazard.
  it("renders every tag with no truncation token", async () => {
    renderInShell(<CustomersSection />);
    await screen.findByText("מיכל לוי");
    const tags = screen.getByTestId("customer-row-tags");
    expect(within(tags).getAllByText(/VIP|כלה/)).toHaveLength(2);
    // The `+` this would have to carry is also the first character of every
    // E.164 phone on the row, which is half of why the token is a bidi hazard.
    expect(tags.textContent ?? "").not.toContain("+");
  });

  it("shows the outage alert and does NOT stack an empty state under it", async () => {
    listCustomers.mockRejectedValue(new ApiError(500, "UNKNOWN", "boom"));
    renderInShell(<CustomersSection />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("לא ניתן לטעון את רשימת הלקוחות כרגע.");
    expect(screen.queryByText("אין עדיין לקוחות")).toBeNull();
    expect(screen.queryByText("אין תוצאות לחיפוש הזה")).toBeNull();
  });

  it("maps a 403 to the Hebrew that names no role", async () => {
    listCustomers.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "Not available."));
    renderInShell(<CustomersSection />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("אין הרשאה לצפות בכרטיסי הלקוחות כרגע.");
    for (const forbidden of ["אחראית משמרת", "תפקיד", "בוטלו", "הוסרה", "שונה"]) {
      expect(alert.textContent ?? "").not.toContain(forbidden);
    }
  });

  // Collapsing the two would tell a boutique with 200 customers that it has
  // none.
  it("distinguishes an empty directory from an empty search result", async () => {
    listCustomers.mockResolvedValue(page([], 0));
    renderInShell(<CustomersSection />);
    expect(await screen.findByText("אין עדיין לקוחות")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("חיפוש לפי שם או טלפון"), {
      target: { value: "נועה" },
    });
    expect(await screen.findByText("אין תוצאות לחיפוש הזה")).toBeInTheDocument();
    expect(screen.queryByText("אין עדיין לקוחות")).toBeNull();
  });

  it("fires exactly one request for a five-keystroke burst", async () => {
    vi.useFakeTimers();
    renderInShell(<CustomersSection />);
    const box = screen.getByLabelText("חיפוש לפי שם או טלפון");
    for (const term of ["מ", "מי", "מיכ", "מיכל", "מיכל "]) {
      fireEvent.change(box, { target: { value: term } });
    }
    expect(listCustomers).not.toHaveBeenCalled();
    // 299 pins the CONSTANT, not merely the existence of a timeout: without it
    // this test passes just as happily against setTimeout(…, 0), which is not a
    // debounce at all.
    await act(async () => {
      vi.advanceTimersByTime(299);
    });
    expect(listCustomers).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(listCustomers).toHaveBeenCalledTimes(1);
    // Trimmed at the api layer, but the term travels as typed from here.
    expect(listCustomers).toHaveBeenCalledWith({ q: "מיכל ", offset: 0, limit: 50 });
  });

  // The server answers 400 for a q over the bound, the catch would set
  // loadError, and the list would render "try again in a moment" — a
  // wait-and-retry message for an input error every retry reproduces.
  it("caps the search box at the mirrored server bound", async () => {
    renderInShell(<CustomersSection />);
    const box = screen.getByLabelText("חיפוש לפי שם או טלפון");
    expect(box).toHaveAttribute("maxlength", String(MAX_SEARCH_TERM_LENGTH));
    // dir stays unset: the term is usually Hebrew, and dir="ltr" on Hebrew free
    // text is itself a bidi defect.
    expect(box).not.toHaveAttribute("dir");
  });

  // `offset` is pinned to 0 and there is no pager, so the announced `total` is
  // the count under the search predicate and NOT the length of the list beneath
  // it. A boutique with 60 customers was told «לקוחות ברשימה: 60» above 50 rows,
  // with nothing saying the rest existed — a sentence that is false about the
  // list it sits on. Same notice shape this screen already uses twice.
  it("says the list is truncated when the count exceeds the rows rendered", async () => {
    listCustomers.mockResolvedValue(page([row()], 60));
    renderInShell(<CustomersSection />);
    await screen.findByText("מיכל לוי");
    expect(screen.getByText("מוצגות 1 מתוך 60 לקוחות.")).toBeInTheDocument();
  });

  it("says nothing about truncation when every customer is on the page", async () => {
    listCustomers.mockResolvedValue(page([row()], 1));
    renderInShell(<CustomersSection />);
    await screen.findByText("מיכל לוי");
    expect(screen.queryByText(/מוצגות .* מתוך/)).toBeNull();
  });

  it("puts the list under a single h2 with no skipped level", async () => {
    renderInShell(<CustomersSection />);
    await screen.findByText("מיכל לוי");
    const levels = screen.getAllByRole("heading").map((h) => Number(h.tagName.slice(1)));
    expect(levels).toEqual([1, 2]);
  });
});

describe("CustomersSection detail swap", () => {
  it("opens the detail from a row and returns to the list", async () => {
    await openDetail();
    expect(screen.getByRole("heading", { level: 2, name: "מיכל לוי" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));
    await screen.findByTestId("customers-count");
    // The list state was never unmounted, so no refetch fires — counted only
    // after the debounce window a refetch would have to schedule itself in.
    await afterTheDebounceWindow();
    expect(listCustomers).toHaveBeenCalledTimes(1);
  });

  // Without the explicit effect, CustomerDetail unmounts with focus on its <h2>
  // and focus drops to <body>: the next Tab restarts at the skip link, WCAG
  // 2.4.3 — the failure BookingDetail.tsx:103-115 already records.
  it("moves focus to the announced count after «חזרה לרשימה»", async () => {
    await openDetail();
    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId("customers-count")),
    );
  });

  it("keeps the back control present while the detail is still loading", async () => {
    getCustomer.mockReturnValue(new Promise(() => {}));
    renderInShell(<CustomersSection />);
    fireEvent.click(await screen.findByText("מיכל לוי"));
    expect(await screen.findByRole("button", { name: "חזרה לרשימה" })).toBeInTheDocument();
    expect(screen.getByText("טוען את פרטי הלקוחה…")).toBeInTheDocument();
  });

  // The only way out of a 404.
  it("keeps the back control present on a NOT_FOUND", async () => {
    getCustomer.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    renderInShell(<CustomersSection />);
    fireEvent.click(await screen.findByText("מיכל לוי"));
    expect(await screen.findByText("הלקוחה הזו לא נמצאה. ייתכן שהכרטיס הוסר.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "חזרה לרשימה" })).toBeInTheDocument();
  });
});

describe("CustomerDetail panels", () => {
  it("renders the phone isolated, the booking history and the message log", async () => {
    await openDetail();
    expect(screen.getByText("+972501234567")).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("מדידה ראשונה")).toBeInTheDocument();
    // Jerusalem, not the runner's New York: 07:00Z is 10:00 there and 03:00
    // here, and 05:30Z on the log row is 08:30 there.
    expect(screen.getByText("10:00")).toBeInTheDocument();
    expect(screen.getByText("08:30")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "יומן הודעות" })).toBeInTheDocument();
    expect(screen.getByText("אישור תור")).toBeInTheDocument();
    expect(screen.getByText("התור שלך אושר")).toBeInTheDocument();
  });

  // 'sent' means the provider accepted the message, not that a handset received
  // it, and the log renders failures — which is why the heading is «יומן הודעות».
  it("reads a failed row as נכשלה in the danger register", async () => {
    getCustomer.mockResolvedValue(
      detail({
        messages: [
          {
            id: "m1",
            created_at: "2026-08-03T07:00:00Z",
            kind: "otp",
            status: "failed",
            body: "קוד: ****",
          },
        ],
      }),
    );
    await openDetail();
    const badge = screen.getByText("נכשלה");
    expect(badge.className).toContain("text-danger");
    expect(screen.getByText("קוד אימות")).toBeInTheDocument();
  });

  it("renders an unknown kind and status as their raw values", async () => {
    getCustomer.mockResolvedValue(
      detail({
        messages: [
          {
            id: "m1",
            created_at: "2026-08-03T07:00:00Z",
            kind: "waitlist_offer",
            status: "delivered",
            body: "…",
          },
        ],
      }),
    );
    await openDetail();
    expect(screen.getByText("waitlist_offer")).toBeInTheDocument();
    expect(screen.getByText("delivered")).toBeInTheDocument();
  });

  it("states the send volume when the window truncated", async () => {
    getCustomer.mockResolvedValue(detail({ messages_total: 214 }));
    await openDetail();
    expect(screen.getByText("מוצגות 1 מתוך 214 רשומות ביומן.")).toBeInTheDocument();
  });

  // The SMS-log notice above has had a test since it shipped; its sibling under
  // the booking panel had none, because no fixture ever reached the limit —
  // which is why changing that branch's `>=` to `>` left every suite green.
  it("states the booking history truncated once it fills the limit", async () => {
    getCustomer.mockResolvedValue(
      detail({
        bookings: Array.from({ length: BOOKING_HISTORY_LIMIT }, (_, index) => ({
          id: `b${index}`,
          starts_at: "2026-08-04T07:00:00Z",
          status: "completed",
          appointment_type_name: "מדידה ראשונה",
        })),
      }),
    );
    await openDetail();
    expect(screen.getByText("מוצגים 50 התורים האחרונים.")).toBeInTheDocument();
  });

  it("says nothing about the booking history when it is short of the limit", async () => {
    await openDetail();
    expect(screen.queryByText(/התורים האחרונים/)).toBeNull();
  });

  it("shows both empty panels when there is no history at all", async () => {
    getCustomer.mockResolvedValue(detail({ bookings: [], messages: [], messages_total: 0 }));
    await openDetail();
    expect(screen.getByText("אין עדיין תורים בכרטיס הזה.")).toBeInTheDocument();
    expect(screen.getByText("אין עדיין רשומות ביומן ההודעות.")).toBeInTheDocument();
  });
});

// --- F20: the §30A consent, on the card the front desk actually opens ---------
//
// ⚠ THIS IS WHERE GATE 1 Q4 BECOMES REACHABLE. The privacy section is owner-only
// because its first step is the §13 export; `POST /manage/privacy/marketing-
// withdraw` deliberately carries NO route-level gate and inherits the router's
// (OWNER, SHIFT_MANAGER) one. A shift manager taking the call has to be able to
// honour «אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת» from the screen she is
// already on, and this card is that screen.

describe("CustomerDetail marketing consent", () => {
  // Effective consent is `at IS NOT NULL AND withdrawn IS NULL`, which is THREE
  // states and not a boolean. Withdrawal is ADDITIVE: wiping the grant timestamp
  // would destroy the Spam-Law evidence that consent existed when a message was
  // sent, so «הוסרה» is a real third state and not the absence of the first.
  //
  // `it.each` and not a loop with a manual unmount: three renders in one `it`
  // share a DOM, and the queries would start matching the previous case's badge.
  it.each([
    [{}, "privacy.consentNone"],
    [{ marketing_consent_at: "2026-02-01T09:00:00Z" }, "privacy.consentActive"],
    [
      {
        marketing_consent_at: "2026-02-01T09:00:00Z",
        marketing_consent_withdrawn_at: "2026-03-01T09:00:00Z",
      },
      "privacy.consentWithdrawn",
    ],
  ] as [Partial<CustomerDetailResponse>, string][])(
    "renders the consent state as its own word, never as a colour (%#)",
    async (patch, expected) => {
      getCustomer.mockResolvedValue(detail(patch));
      await openDetail();

      expect(screen.getByTestId("customer-consent")).toHaveTextContent(i18n.t(expected));
    },
  );

  it("offers the withdrawal only where there is a live consent to withdraw", async () => {
    getCustomer.mockResolvedValue(detail());
    await openDetail();

    expect(screen.queryByRole("button", { name: i18n.t("privacy.withdraw") })).toBeNull();
  });

  it("withdraws through the id the card already holds, with no confirmation step", async () => {
    // §30A says revocation may not be conditioned, and a modal at the counter is
    // a condition however small. Keyed on `customer_id` — the card has it, so
    // the front desk needs no lookup and no privacy section.
    withdrawMarketingConsent.mockResolvedValue({ changed: true });
    getCustomer.mockResolvedValue(detail({ marketing_consent_at: "2026-02-01T09:00:00Z" }));
    updateCustomer.mockClear();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.withdraw") }));

    await waitFor(() => {
      expect(withdrawMarketingConsent).toHaveBeenCalledWith({ customer_id: CUSTOMER_ID });
    });
    // The badge moves to «הוסרה» without a refetch: the response is one boolean,
    // and re-reading the whole card to learn what we just did would blank the
    // booking history and the message log for the length of a round trip.
    expect(await screen.findByText(i18n.t("privacy.consentWithdrawn"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: i18n.t("privacy.withdraw") })).toBeNull();
  });

  it("keeps the card readable when the withdrawal fails", async () => {
    withdrawMarketingConsent.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    getCustomer.mockResolvedValue(detail({ marketing_consent_at: "2026-02-01T09:00:00Z" }));
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("privacy.withdraw") }));

    expect(await screen.findByText(i18n.t("privacy.withdrawFailed"))).toBeInTheDocument();
    // The state did NOT move: a badge that flipped optimistically would tell a
    // staffer she had honoured a §30A revocation that never landed.
    expect(screen.getByTestId("customer-consent")).toHaveTextContent(i18n.t("privacy.consentActive"));
  });
});

describe("CustomerDetail tag editor", () => {
  async function addTag(value: string) {
    fireEvent.change(screen.getByLabelText("תגית חדשה"), { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה" }));
  }

  it("adds a chip to the end and clears the input", async () => {
    await openDetail();
    await addTag("כלה");
    const chips = within(screen.getByTestId("customer-tags")).getAllByText(/VIP|כלה/);
    expect(chips.map((chip) => chip.textContent)).toEqual(["VIP", "כלה"]);
    expect(screen.getByLabelText("תגית חדשה")).toHaveValue("");
  });

  it("removes a chip through a button whose aria-label starts with its visible label", async () => {
    await openDetail();
    const remove = screen.getByRole("button", { name: "הסרה של התגית VIP" });
    // WCAG 2.5.3: the accessible name starts with the visible one.
    expect(remove.textContent).toBe("הסרה");
    fireEvent.click(remove);
    expect(screen.getByText("אין תגיות בכרטיס הזה.")).toBeInTheDocument();
  });

  it("rejects a case-insensitive duplicate in the tag input's own error slot", async () => {
    await openDetail();
    await addTag("vip");
    const input = screen.getByLabelText("תגית חדשה");
    expect(input).toHaveAccessibleDescription(/התגית הזו כבר קיימת בכרטיס\./);
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("rejects an over-long tag with the bound in the message", async () => {
    await openDetail();
    await addTag("א".repeat(MAX_TAG_LENGTH + 1));
    expect(screen.getByLabelText("תגית חדשה")).toHaveAccessibleDescription(
      new RegExp(`עד ${MAX_TAG_LENGTH} תווים`),
    );
  });

  // A text <input> sanitizes CR and LF out of its own value, so the control
  // character that actually reaches this guard is the one a PDF or a Word paste
  // carries: U+000C, or DEL.
  it("rejects a control character in a tag", async () => {
    await openDetail();
    await addTag("כלה\x0cשנייה");
    expect(screen.getByLabelText("תגית חדשה")).toHaveAccessibleDescription(
      /התגית מכילה תווים שאי אפשר לשמור\./,
    );
  });

  it("names the remedy when the card is full", async () => {
    getCustomer.mockResolvedValue(
      detail({ tags: Array.from({ length: MAX_TAGS }, (_, i) => `תגית${i}`) }),
    );
    await openDetail();
    await addTag("אחת יותר");
    expect(screen.getByLabelText("תגית חדשה")).toHaveAccessibleDescription(
      /אפשר להסיר תגית קיימת ולנסות שוב\./,
    );
  });

  it("treats a blank tag as a no-op rather than an error", async () => {
    await openDetail();
    await addTag("   ");
    const input = screen.getByLabelText("תגית חדשה");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).toHaveAccessibleDescription("עד 10 תגיות, עד 24 תווים לתגית.");
  });
});

describe("CustomerDetail save", () => {
  it("sends only the fields that moved and patches state from the response", async () => {
    await openDetail();
    updateCustomer.mockResolvedValue(detail({ notes: "אוהבת תחרה", tags: ["VIP"] }));
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "אוהבת תחרה" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));

    await waitFor(() => expect(updateCustomer).toHaveBeenCalledTimes(1));
    expect(updateCustomer).toHaveBeenCalledWith(CUSTOMER_ID, { notes: "אוהבת תחרה" });
    await waitFor(() => expect(screen.getByLabelText("הערות")).toHaveValue("אוהבת תחרה"));
  });

  // The response is the WHOLE detail, so the drafts are re-seeded from it and
  // never kept. Pinned through the case where the two genuinely differ: this
  // patch carries NOTES only, and the tags came back with a chip the local
  // draft never had — a second staff member added it between the read and the
  // write. Re-seeding only the fields this client sent would render a card that
  // disagrees with the row it just saved.
  it("re-seeds every draft from the response, including fields it did not send", async () => {
    await openDetail();
    // The patch carries TAGS only, and the response carries a note and a chip
    // the local draft never had — a second staff member edited the card between
    // this read and this write.
    updateCustomer.mockResolvedValue(
      detail({ notes: "מעדיפה תור בערב", tags: ["VIP", "דחוף", "כלה"] }),
    );
    fireEvent.change(screen.getByLabelText("תגית חדשה"), { target: { value: "דחוף" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה" }));
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateCustomer).toHaveBeenCalledWith(CUSTOMER_ID, { tags: ["VIP", "דחוף"] }),
    );
    expect(await screen.findByRole("button", { name: "הסרה של התגית כלה" })).toBeInTheDocument();
    expect(screen.getByLabelText("הערות")).toHaveValue("מעדיפה תור בערב");
  });

  // setDetail(updated) is what makes the SECOND save honest: without it the
  // baseline the diff compares against stays at the pre-save values, so an
  // untouched card re-sends the change it already saved and writes a second
  // audit row for an edit nobody made. It is also what keeps the read-only
  // panels live — the PATCH answers the WHOLE detail for exactly this reason.
  it("replaces the whole detail from the response, panels included", async () => {
    await openDetail();
    updateCustomer.mockResolvedValue(
      detail({
        notes: "אוהבת תחרה",
        messages_total: 2,
        messages: [
          {
            id: "m2",
            created_at: "2026-08-03T05:30:00Z",
            kind: "reminder",
            status: "queued",
            body: "תזכורת לתור מחר",
          },
        ],
      }),
    );
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "אוהבת תחרה" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));

    expect(await screen.findByText("תזכורת לתור מחר")).toBeInTheDocument();
    expect(screen.getByText("בהמתנה")).toBeInTheDocument();

    // Nothing moved since, so the second press must send nothing at all.
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "שמירה" })).toBeEnabled());
    expect(updateCustomer).toHaveBeenCalledTimes(1);
  });

  // An all-unchanged patch is a no-op the server answers 200 without writing an
  // audit row, so sending less is what keeps the audit table meaningful.
  it("fires no request at all when nothing moved", async () => {
    await openDetail();
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "שמירה" })).toBeEnabled());
    expect(updateCustomer).not.toHaveBeenCalled();
  });

  // maxLength bounds LENGTH but does not filter control characters, so a note
  // pasted out of Word carrying U+000B would reach the server and come back as
  // an ENGLISH pydantic sentence in a Hebrew console.
  it("refuses a pasted control character before any request leaves", async () => {
    await openDetail();
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "הודבק\x0bמ-Word" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));
    await waitFor(() =>
      expect(screen.getByLabelText("הערות")).toHaveAccessibleDescription(
        /ההערות מכילות תווים שאי אפשר לשמור\./,
      ),
    );
    expect(updateCustomer).not.toHaveBeenCalled();
  });

  // tabIndex={-1} is load-bearing: a <p> is not focusable, so .focus() on a
  // plain paragraph is a silent no-op that drops focus to <body>.
  it("moves focus to the save alert when the write fails", async () => {
    await openDetail();
    updateCustomer.mockRejectedValue(new ApiError(500, "UNKNOWN", "boom"));
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "משהו אחר" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));

    const alert = await screen.findByTestId("customer-save-error");
    // Every unmapped code reads as the Hebrew save-failed sentence. It used to
    // fall through to the server's English on the theory that VALIDATION_ERROR
    // was the only code this path could produce — it is not, see the 401 below.
    expect(alert).toHaveTextContent("לא ניתן לשמור את השינויים כרגע.");
    expect(alert.textContent ?? "").not.toContain("boom");
    await waitFor(() => expect(document.activeElement).toBe(alert));
  });

  // The concrete failure: her session expires while the card is open, she
  // presses «שמירה», the PATCH answers 401 NOT_AUTHENTICATED — and the alert the
  // focus move lands on rendered the English "Authentication required." into a
  // Hebrew RTL console. `customers.saveFailed` shipped in both bundles with
  // nothing resolving it.
  it("renders the Hebrew save-failed sentence when the session has expired", async () => {
    await openDetail();
    updateCustomer.mockRejectedValue(
      new ApiError(401, "NOT_AUTHENTICATED", "Authentication required."),
    );
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "משהו אחר" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));

    const alert = await screen.findByTestId("customer-save-error");
    expect(alert).toHaveTextContent("לא ניתן לשמור את השינויים כרגע.");
    expect(alert.textContent ?? "").not.toContain("Authentication");
  });

  // NOT_FOUND stays mapped: the card is gone, which is a different fact from
  // "the save did not land", and the fallback must not swallow it.
  it("still maps a NOT_FOUND on save to its own sentence", async () => {
    await openDetail();
    updateCustomer.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "משהו אחר" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));

    const alert = await screen.findByTestId("customer-save-error");
    expect(alert).toHaveTextContent("הלקוחה הזו לא נמצאה. ייתכן שהכרטיס הוסר.");
  });

  it("patches the list row from the save response without refetching", async () => {
    listCustomers.mockResolvedValue(page([row({ tags: ["VIP"] })]));
    await openDetail();
    updateCustomer.mockResolvedValue(detail({ tags: ["VIP", "כלה"] }));
    fireEvent.change(screen.getByLabelText("תגית חדשה"), { target: { value: "כלה" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה" }));
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));
    await waitFor(() => expect(updateCustomer).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימה" }));
    await screen.findByTestId("customers-count");
    expect(screen.getByText("כלה")).toBeInTheDocument();
    await afterTheDebounceWindow();
    expect(listCustomers).toHaveBeenCalledTimes(1);
  });
});

describe("CustomersSection accessibility", () => {
  it("passes axe with zero violations on the loaded list", async () => {
    const { container } = renderInShell(<CustomersSection />);
    await screen.findByText("מיכל לוי");
    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the empty directory", async () => {
    listCustomers.mockResolvedValue(page([], 0));
    const { container } = renderInShell(<CustomersSection />);
    await screen.findByText("אין עדיין לקוחות");
    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the detail", async () => {
    const { container } = renderInShell(<CustomersSection />);
    fireEvent.click(await screen.findByText("מיכל לוי"));
    await screen.findByRole("heading", { level: 3, name: "יומן הודעות" });
    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("puts the detail under a single h2 with no skipped level", async () => {
    await openDetail();
    const levels = screen.getAllByRole("heading").map((h) => Number(h.tagName.slice(1)));
    expect(levels).toEqual([1, 2, 3, 3]);
  });

  it("focuses the detail heading on mount so the owner hears where she landed", async () => {
    await openDetail();
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 2, name: "מיכל לוי" }),
    );
  });
});
