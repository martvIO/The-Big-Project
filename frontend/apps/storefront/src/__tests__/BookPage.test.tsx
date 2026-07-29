import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { themeTokens } from "@boutique/ui";
import type { AppointmentTypeRow, BoutiqueResponse, StorefrontTerms } from "../api";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { SlotPicker } from "../components/booking/SlotPicker";
import { TypePicker } from "../components/booking/TypePicker";
import { BookPage } from "../routes/BookPage";

// Spread the real module so ApiError and errorMessage* keep their real
// implementations — the load-failure copy under test is chosen by CODE mapping,
// and a stubbed mapper would assert nothing about it.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTerms: vi.fn(),
      listAppointmentTypes: vi.fn(),
      listSlots: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const getTerms = vi.mocked(api.getTerms);
const listTypes = vi.mocked(api.listAppointmentTypes);
const listSlots = vi.mocked(api.listSlots);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const TERMS: StorefrontTerms = {
  version: 3,
  terms_text: "ביטול עד 48 שעות לפני המועד.",
  refundable_until_hours_before: 48,
  forfeit_percent: 50,
};

const DOWN = new ApiError(503, "UNKNOWN", "backend down");
const THROTTLED = new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts. Try again later.");
const GONE = new ApiError(404, "NOT_FOUND", "Resource not found.");

function boutique(overrides: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: "052-1234567",
    address: "דיזנגוף 100, תל אביב",
    maps_url: null,
    instagram: "alma.bridal",
    hours: [],
    exceptions: [],
    ...overrides,
  };
}

function appointmentType(overrides: Partial<AppointmentTypeRow> = {}): AppointmentTypeRow {
  return {
    id: "t1",
    name: "מדידה ראשונה",
    duration_minutes: 45,
    audience: "all",
    deposit_required: false,
    deposit_amount_agorot: null,
    ...overrides,
  };
}

// Jerusalem runs UTC+3 in August; the suite's own clock is America/New_York.
// 07:00Z is 10:00 on the 4th in Jerusalem and 03:00 on the 4th in New York;
// 21:00Z is 00:00 on the FIFTH in Jerusalem and still 17:00 on the fourth in
// New York — the instant that tells the boutique's calendar from the device's.
const AUG4_1000 = "2026-08-04T07:00:00Z";
const AUG4_1045 = "2026-08-04T07:45:00Z";
const AUG5_1000 = "2026-08-05T07:00:00Z";
const AUG5_0000 = "2026-08-04T21:00:00Z";

const SLOTS = [AUG4_1000, AUG4_1045, AUG5_1000];

function pending<T>(): Promise<T> {
  return new Promise<T>(() => {
    // never settles — holds the step in its loading state
  });
}

function renderBook(step: Parameters<typeof BookPage>[0]["step"] = "slot", dressId?: string) {
  // The step reads the boutique from the layout's single fetch, so the layout
  // is part of the unit under test — a bare <BookPage/> renders against a
  // context default that never resolves.
  return render(
    <StorefrontLayout>
      <BookPage step={step} dressId={dressId} />
    </StorefrontLayout>,
  );
}

async function pickFirstType() {
  fireEvent.click(await screen.findByRole("radio", { name: /מדידה ראשונה/ }));
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  getTerms.mockResolvedValue(TERMS);
  listTypes.mockResolvedValue([appointmentType()]);
  listSlots.mockResolvedValue({ slots: SLOTS.map((starts_at) => ({ starts_at })) });
  window.history.replaceState(null, "", "/book/slot");
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("BookPage shell", () => {
  it.each([
    ["slot", "booking.stepSlot"],
    ["details", "booking.stepDetails"],
    ["terms", "booking.stepTerms"],
    ["verify", "booking.stepOtp"],
    ["confirm", "booking.confirmTitle"],
  ] as const)("titles the %s step with its own h1", (step, key) => {
    renderBook(step);

    // The h1 is the step, never the boutique: a static string has no state
    // where a failed fetch leaves the page untitled.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t(key));
  });

  it("marks the current step in an inert stepper", () => {
    renderBook("terms");

    const stepper = screen.getByRole("list", { name: i18n.t("booking.stepsLabel") });
    expect(within(stepper).queryAllByRole("link")).toHaveLength(0);
    expect(stepper.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
    expect(stepper.querySelector('[aria-current="step"]')).toHaveTextContent(
      i18n.t("booking.stepTerms"),
    );
  });

  it("drops the stepper on confirm — it is terminal, outside the flow", () => {
    renderBook("confirm");
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});

describe("BookPage slot step — happy paths", () => {
  it("advances to the details step with a type and a time chosen", async () => {
    renderBook();

    await pickFirstType();
    fireEvent.click(screen.getByRole("radio", { name: "10:45" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));

    expect(window.location.pathname).toBe("/book/details");
  });

  it("carries the bound dress into the forward URL on the item-based path", async () => {
    renderBook("slot", "d 1");

    await pickFirstType();
    fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));

    // Encoded exactly as api.getDress encodes it; router.tsx's decodeId is the
    // matching decoder.
    expect(window.location.pathname).toBe("/book/details/d%201");
  });

  it("opens with nothing preselected — choosing the first type would choose for her", async () => {
    listTypes.mockResolvedValue([
      appointmentType({ audience: "brides_only" }),
      appointmentType({ id: "t2", name: "חבילת כלה", duration_minutes: 120 }),
    ]);

    renderBook();

    for (const radio of await screen.findAllByRole("radio")) {
      expect(radio).not.toBeChecked();
    }
  });

  it("reads the boutique calendar, not the device — a 21:00Z slot is the NEXT day", async () => {
    listSlots.mockResolvedValue({
      slots: [{ starts_at: AUG4_1000 }, { starts_at: AUG5_0000 }],
    });

    renderBook();

    // 21:00Z is 17:00 on the 4th in New York, where the suite runs. Reading the
    // device clock would put it on the 4th at 17:00.
    expect(await screen.findByRole("radio", { name: "10:00" })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "17:00" })).toBeNull();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-05" },
    });
    expect(screen.getByRole("radio", { name: "00:00" })).toBeInTheDocument();
  });

  it("isolates every time as an LTR run inside the Hebrew page", async () => {
    renderBook();

    const chip = await screen.findByRole("radio", { name: "10:45" });
    const bdi = chip.closest("label")?.querySelector("bdi");
    expect(bdi).toHaveAttribute("dir", "ltr");
    expect(bdi).toHaveTextContent("10:45");
  });

  it("lays the grid out on one auto-fill rule — 104px minimum, no breakpoints", async () => {
    const { container } = renderBook();

    await screen.findByRole("radio", { name: "10:00" });
    const grid = container.querySelector('[class*="repeat(auto-fill"]');
    // R10: the column count is a consequence of this rule and the Card padding,
    // never a hand-set number per breakpoint.
    expect(grid?.className).toContain("repeat(auto-fill,minmax(104px,1fr))");
    expect(grid?.className).toContain("gap-2");
  });

  it("keeps the Card at --space-6 at every width", async () => {
    const { container } = renderBook();

    await screen.findByRole("radio", { name: "10:00" });
    // R9: Card hardcodes p-6 and cn has no tailwind-merge, so a caller's p-4
    // ships BOTH classes and loses on stylesheet order. Never pass one.
    const card = container.querySelector(".bg-surface.p-6");
    expect(card).not.toBeNull();
    expect(container.querySelector(".p-4")).toBeNull();
  });
});

describe("BookPage slot step — the appointment-type picker", () => {
  it("labels a brides-only type without gating it", async () => {
    listTypes.mockResolvedValue([appointmentType({ audience: "brides_only" })]);

    renderBook();

    const radio = await screen.findByRole("radio", { name: /מדידה ראשונה/ });
    expect(radio).toBeEnabled();
    expect(radio).toHaveAccessibleName(new RegExp(i18n.t("booking.audienceBrides")));

    // D10: it labels, it does not gate.
    fireEvent.click(radio);
    fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));
    expect(window.location.pathname).toBe("/book/details");
  });

  it("states each duration in minutes", async () => {
    listTypes.mockResolvedValue([appointmentType({ duration_minutes: 90 })]);

    renderBook();

    expect(
      await screen.findByText(i18n.t("booking.typeDuration", { minutes: 90 })),
    ).toBeInTheDocument();
  });

  it("reveals the deposit branch under ITS OWN row while a sibling stays bookable", async () => {
    listTypes.mockResolvedValue([
      appointmentType(),
      appointmentType({
        id: "t2",
        name: "חבילת כלה",
        duration_minutes: 120,
        deposit_required: true,
        deposit_amount_agorot: 150000,
      }),
    ]);

    renderBook();

    const deposit = await screen.findByRole("radio", { name: /חבילת כלה/ });
    fireEvent.click(deposit);

    // The reveal belongs to the row, tied by aria-describedby — never nested
    // inside the <label>, which would fold the whole panel into the accessible
    // name.
    expect(screen.getByText(new RegExp(i18n.t("booking.depositByPhone")))).toBeInTheDocument();
    expect(deposit).toHaveAccessibleDescription(new RegExp(i18n.t("booking.depositByPhone")));
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toHaveAttribute(
      "href",
      "tel:052-1234567",
    );
    // P4: through <Price>, because qa-greps.sh bans the glyph outright.
    expect(screen.getByText(/1,500/)).toBeInTheDocument();

    // The forward control is never disabled (R7); pressing it here re-announces
    // the deposit block and does nothing else.
    const forward = screen.getByRole("button", { name: i18n.t("booking.continue") });
    expect(forward).toBeEnabled();
    expect(forward).not.toHaveAttribute("aria-describedby");
    fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
    fireEvent.click(forward);
    expect(window.location.pathname).toBe("/book/slot");
    expect(document.activeElement).toBe(deposit);

    // …AND THE SIBLING STAYS BOOKABLE. This is the assertion that catches a
    // branch applied to the whole picker instead of one row.
    const sibling = screen.getByRole("radio", { name: /מדידה ראשונה/ });
    expect(sibling).toBeEnabled();
    fireEvent.click(sibling);
    expect(screen.queryByText(new RegExp(i18n.t("booking.depositByPhone")))).toBeNull();
    // The time picked while the deposit row was selected survives the switch.
    expect(screen.getByRole("radio", { name: "10:00" })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));
    expect(window.location.pathname).toBe("/book/details");
  });

  it("replaces the deposit panel with plain copy when the boutique fetch failed", async () => {
    loadBoutique.mockRejectedValue(DOWN);
    listTypes.mockResolvedValue([
      appointmentType({ deposit_required: true, deposit_amount_agorot: 150000 }),
    ]);

    renderBook();

    fireEvent.click(await screen.findByRole("radio", { name: /מדידה ראשונה/ }));

    // D12: ContactPanel with every channel absent renders an empty flex box, so
    // the degrade has to be a branch at the call site.
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });
});

describe("BookPage slot step — R7, the forward control is never disabled", () => {
  it("names both unfilled groups and moves focus to the first of them", async () => {
    renderBook();

    const forward = await screen.findByRole("button", { name: i18n.t("booking.continue") });
    expect(forward).toBeEnabled();
    fireEvent.click(forward);

    expect(screen.getByText(i18n.t("booking.typeRequired"))).toHaveAttribute("role", "alert");
    expect(screen.getByText(i18n.t("booking.timeRequired"))).toHaveAttribute("role", "alert");
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: /מדידה ראשונה/ }));
    expect(window.location.pathname).toBe("/book/slot");
  });

  it("falls through to the time group once the type is chosen", async () => {
    renderBook();

    await pickFirstType();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("booking.continue") }));

    expect(screen.queryByText(i18n.t("booking.typeRequired"))).toBeNull();
    expect(screen.getByText(i18n.t("booking.timeRequired"))).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "10:00" }));
    expect(window.location.pathname).toBe("/book/slot");
  });

  it("clears the messages once the choice is made", async () => {
    renderBook();

    fireEvent.click(await screen.findByRole("button", { name: i18n.t("booking.continue") }));
    await pickFirstType();
    fireEvent.click(screen.getByRole("radio", { name: "10:45" }));

    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("BookPage slot step — states", () => {
  it("announces the load with a visually-hidden status, never aria-busy alone", async () => {
    getTerms.mockReturnValue(pending());

    const { container } = renderBook();

    // R30: aria-busy on a plain div is announced by neither VoiceOver nor NVDA,
    // so a bride on a slow connection heard the h1, then silence.
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(i18n.t("catalog.loading"));
    expect(status.closest(".sr-only")).not.toBeNull();
    expect(container.querySelectorAll(".animate-skeleton").length).toBeGreaterThan(0);
    // Nothing to advance to yet.
    expect(screen.queryByRole("button", { name: i18n.t("booking.continue") })).toBeNull();
  });

  it("replaces the flow with the phone-only entry when no terms are published", async () => {
    getTerms.mockRejectedValue(GONE);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTermsByPhone"))).toBeInTheDocument();
    // D5 is branched on the 404 at the call site, before errorMessageKey — the
    // shared helper cannot tell this NOT_FOUND from any other in the flow.
    expect(screen.queryByText(i18n.t("errors.notFound"))).toBeNull();
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    // No stepper, and R12's heading: a step label above "call us" would name a
    // step that is not on the page.
    expect(screen.queryByRole("list", { name: i18n.t("booking.stepsLabel") })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("document.book"));
    expect(screen.queryByRole("button", { name: i18n.t("booking.continue") })).toBeNull();
    expect(screen.getByRole("link", { name: /קולקציה/ })).toHaveAttribute("href", "/");
  });

  it("degrades the no-terms entry to plain copy with no boutique", async () => {
    getTerms.mockRejectedValue(GONE);
    loadBoutique.mockRejectedValue(DOWN);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTermsByPhone"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: i18n.t("contact.call") })).toBeNull();
  });

  it("replaces the Card with the phone-only block when there are no active types", async () => {
    listTypes.mockResolvedValue([]);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTypes"))).toBeInTheDocument();
    // FINDING 4: the sentence carries no phone invitation of its own — the
    // panel beneath it does that job.
    expect(screen.getByRole("link", { name: i18n.t("contact.call") })).toBeInTheDocument();
    expect(screen.queryByLabelText(i18n.t("booking.pickDate"))).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("booking.continue") })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("document.book"));
  });

  it("degrades the no-types block to plain copy with no boutique", async () => {
    listTypes.mockResolvedValue([]);
    loadBoutique.mockRejectedValue(DOWN);

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noTypes"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.contactUnavailable"))).toBeInTheDocument();
  });

  it("states the empty window as a fact — no icon, no retry, picker and date intact", async () => {
    listSlots.mockResolvedValue({ slots: [] });

    renderBook();

    expect(await screen.findByText(i18n.t("booking.noSlots"))).toBeInTheDocument();
    // The state every new tenant ships in, so it must read as a fact, not a fault.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("catalog.retry") })).toBeNull();
    expect(screen.getByRole("radio", { name: /מדידה ראשונה/ })).toBeInTheDocument();
    expect(screen.getByLabelText(i18n.t("booking.pickDate"))).toBeInTheDocument();
  });

  it("shows the same sentence for a date inside the window with no times", async () => {
    renderBook();

    await screen.findByRole("radio", { name: "10:00" });
    // F-A5: a native date input cannot disable arbitrary dates, so she can
    // always land on an empty one. Whole-window-empty and this-date-empty are
    // the same block and the same string.
    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-06" },
    });

    expect(screen.getByText(i18n.t("booking.noSlots"))).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "10:00" })).toBeNull();
  });

  it("bounds the date control to the window the server actually returned", async () => {
    renderBook();

    const date = await screen.findByLabelText(i18n.t("booking.pickDate"));
    expect(date).toHaveValue("2026-08-04");
    expect(date).toHaveAttribute("min", "2026-08-04");
    expect(date).toHaveAttribute("max", "2026-08-05");
    expect(date).toHaveAttribute("dir", "ltr");
  });

  it("drops a time picked on another date rather than carrying it forward", async () => {
    renderBook();

    fireEvent.click(await screen.findByRole("radio", { name: "10:45" }));
    fireEvent.change(screen.getByLabelText(i18n.t("booking.pickDate")), {
      target: { value: "2026-08-05" },
    });

    expect(screen.getByRole("radio", { name: "10:00" })).not.toBeChecked();
  });

  it("raises ONE muted alert with a retry when an entry read fails", async () => {
    listSlots.mockRejectedValue(DOWN);

    renderBook();

    const alerts = await screen.findAllByRole("alert");
    // One outage announced three times makes a screen reader read three
    // messages for one problem.
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toHaveTextContent(i18n.t("booking.slotsError"));
    // A backend that is down is not the boutique's fault.
    expect(alerts[0].className).toContain("text-ink-muted");
    expect(alerts[0].className).not.toContain("danger");
    expect(screen.getByRole("button", { name: i18n.t("catalog.retry") })).toBeInTheDocument();
  });

  it("re-runs every entry read from the retry button", async () => {
    listTypes.mockRejectedValueOnce(DOWN);

    renderBook();
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("catalog.retry") }));

    expect(await screen.findByRole("radio", { name: "10:00" })).toBeInTheDocument();
    expect(listTypes).toHaveBeenCalledTimes(2);
    expect(getTerms).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });

  it("says a spent budget in the load-failure block, muted, with no second key", async () => {
    listSlots.mockRejectedValue(THROTTLED);

    renderBook();

    const alert = await screen.findByRole("alert");
    // errorMessageOr already maps TOO_MANY_ATTEMPTS — do not add a second case.
    expect(alert).toHaveTextContent(i18n.t("errors.tooManyAttempts"));
    expect(alert.className).toContain("text-ink-muted");
    expect(screen.getByRole("button", { name: i18n.t("catalog.retry") })).toBeInTheDocument();
  });
});

// The two mid-flow returns land on this step from the verify step's submit
// (§6, Tasks 9-11). Their markup is the pickers' own `error` slot, so it is
// pinned here against the real Hebrew rather than waiting for the caller.
describe("BookPage slot step — the mid-flow returns", () => {
  let sheet: HTMLStyleElement;

  beforeEach(() => {
    // jsdom loads no stylesheet, so every class computes to the UA default and
    // a colour assertion would pass whichever class the line carried.
    sheet = document.createElement("style");
    sheet.textContent = `
      .text-danger { color: ${themeTokens["--color-danger"]}; }
      .text-ink-muted { color: ${themeTokens["--color-ink-muted"]}; }
    `;
    document.head.append(sheet);
  });

  afterEach(() => {
    sheet.remove();
  });

  function colourOf(className: string): string {
    const probe = document.createElement("span");
    probe.className = className;
    document.body.append(probe);
    const { color } = getComputedStyle(probe);
    probe.remove();
    return color;
  }

  it("puts errors.slotUnavailable above the time legend, in danger", () => {
    render(
      <StorefrontLayout>
        <SlotPicker
          date="2026-08-04"
          times={[{ value: AUG4_1000, label: "10:00" }]}
          value={null}
          error={i18n.t("errors.slotUnavailable")}
          onDateChange={() => undefined}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("errors.slotUnavailable"));
    // A conflict she must act on is danger; an outage is muted. Guards the
    // guard: an inert stylesheet would make both sides equal.
    expect(colourOf("text-danger")).not.toBe(colourOf("text-ink-muted"));
    expect(getComputedStyle(alert).color).toBe(colourOf("text-danger"));
    // Above the legend, not inside the fieldset — a <legend> that is not the
    // first element child stops naming its group.
    expect(alert.compareDocumentPosition(screen.getByText(i18n.t("booking.pickTime")))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("puts booking.typeGoneRepick above the picker legend, in danger", () => {
    render(
      <StorefrontLayout>
        <TypePicker
          types={[appointmentType()]}
          value={null}
          error={i18n.t("booking.typeGoneRepick")}
          boutique={boutique()}
          onChange={() => undefined}
        />
      </StorefrontLayout>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("booking.typeGoneRepick"));
    expect(getComputedStyle(alert).color).toBe(colourOf("text-danger"));
    expect(alert.compareDocumentPosition(screen.getByText(i18n.t("booking.typeHeading")))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });
});
