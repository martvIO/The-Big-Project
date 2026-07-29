import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { themeTokens } from "@boutique/ui";
import type {
  AppointmentTypeRow,
  BoutiqueResponse,
  StorefrontDetail,
  StorefrontTerms,
} from "../api";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { SlotPicker } from "../components/booking/SlotPicker";
import { TypePicker } from "../components/booking/TypePicker";
import { BookPage } from "../routes/BookPage";
import { matchRoute, usePathname } from "../router";

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
      getDress: vi.fn(),
      createBooking: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const getTerms = vi.mocked(api.getTerms);
const listTypes = vi.mocked(api.listAppointmentTypes);
const listSlots = vi.mocked(api.listSlots);
const getDress = vi.mocked(api.getDress);
const createBooking = vi.mocked(api.createBooking);
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

function dressDetail(overrides: Partial<StorefrontDetail> = {}): StorefrontDetail {
  return {
    id: "d1",
    name: "שמלת אלמה",
    description: null,
    price_agorot: null,
    reserved: false,
    sizes: [
      { size_label: "36", available: true },
      { size_label: "38", available: false },
    ],
    media: [],
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

// The steps are walked, never rendered cold: BookPage holds the whole flow in
// memory, so a later step is only honest when the earlier ones put it there.
// This is what the Router does — the same element in the same position — which
// is why the picked slot, the typed name and the accepted version survive.
function BookFlow() {
  const match = matchRoute(usePathname());
  return match.name === "book" ? <BookPage step={match.step} dressId={match.dressId} /> : null;
}

function renderFlow(path = "/book/slot") {
  window.history.replaceState(null, "", path);
  return render(
    <StorefrontLayout>
      <BookFlow />
    </StorefrontLayout>,
  );
}

async function pickFirstType() {
  fireEvent.click(await screen.findByRole("radio", { name: /מדידה ראשונה/ }));
}

function forward() {
  return screen.getByRole("button", { name: i18n.t("booking.continue") });
}

async function walkToDetails(dressId?: string) {
  const result = renderFlow(
    dressId === undefined ? "/book/slot" : `/book/slot/${encodeURIComponent(dressId)}`,
  );
  await pickFirstType();
  fireEvent.click(screen.getByRole("radio", { name: "10:00" }));
  fireEvent.click(forward());
  return result;
}

async function walkToTerms(dressId?: string) {
  const result = await walkToDetails(dressId);
  fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
  if (dressId !== undefined) {
    const size = screen.queryByRole("radio", { name: /^36/ });
    if (size !== null) fireEvent.click(size);
  }
  fireEvent.click(forward());
  return result;
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  getTerms.mockResolvedValue(TERMS);
  listTypes.mockResolvedValue([appointmentType()]);
  listSlots.mockResolvedValue({ slots: SLOTS.map((starts_at) => ({ starts_at })) });
  getDress.mockResolvedValue(dressDetail());
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

describe("BookPage details step", () => {
  it("advances to the terms step with a name", async () => {
    await walkToDetails();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());

    expect(window.location.pathname).toBe("/book/terms");
  });

  it("labels both fields visibly — a placeholder is never a label", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    expect(name).toHaveAttribute("maxLength", "80");
    expect(name).not.toHaveAttribute("placeholder");
    const notes = screen.getByLabelText(i18n.t("booking.notes"));
    expect(notes).toHaveAttribute("maxLength", "500");
    expect(notes).toHaveAccessibleDescription(new RegExp(i18n.t("booking.notesHint")));
    // The counter is on notes only: 80 characters is not a budget anyone plans
    // against, and a counter under a name reads as a rule about her name.
    expect(screen.getByText("0 / 500")).toBeInTheDocument();
  });

  it("leaves the phone field to the verify step", async () => {
    await walkToDetails();

    expect(screen.queryByLabelText(i18n.t("booking.phone"))).toBeNull();
    expect(screen.queryByText(i18n.t("booking.phoneHint"))).toBeNull();
  });

  it("raises nothing on input or on blur — only on the forward press", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    fireEvent.change(name, { target: { value: "" } });
    fireEvent.blur(name);
    expect(screen.queryByRole("alert")).toBeNull();

    fireEvent.click(forward());
    expect(screen.getByText(i18n.t("booking.nameRequired"))).toHaveAttribute("role", "alert");
    expect(document.activeElement).toBe(name);
    expect(window.location.pathname).toBe("/book/details");
  });

  it("blank-checks the trimmed value and length-checks the raw one", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    // Whitespace only: blank on the TRIMMED value, exactly as validation.py.
    fireEvent.change(name, { target: { value: "   " } });
    fireEvent.click(forward());
    expect(screen.getByText(i18n.t("booking.nameRequired"))).toBeInTheDocument();

    // 79 real characters between two spaces: 81 RAW, 79 trimmed. Length runs on
    // the raw value, so this is refused — a client that validated the trimmed
    // string would send 81 characters the server rejects.
    fireEvent.change(name, { target: { value: ` ${"א".repeat(79)} ` } });
    fireEvent.click(forward());
    expect(screen.getByText(i18n.t("booking.nameTooLong"))).toBeInTheDocument();
    expect(window.location.pathname).toBe("/book/details");
  });

  it("submits 80 characters of name and refuses 81 with no request issued", async () => {
    await walkToDetails();

    const name = screen.getByLabelText(i18n.t("booking.name"));
    fireEvent.change(name, { target: { value: "א".repeat(81) } });
    fireEvent.click(forward());

    expect(screen.getByText(i18n.t("booking.nameTooLong"))).toBeInTheDocument();
    // The anti-vacuous half: not merely that an error rendered, but that the
    // flow issued nothing and went nowhere.
    expect(createBooking).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/book/details");

    fireEvent.change(name, { target: { value: "א".repeat(80) } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms");
  });

  it("submits 500 characters of notes and refuses 501 with no request issued", async () => {
    await walkToDetails();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    const notes = screen.getByLabelText(i18n.t("booking.notes"));
    fireEvent.change(notes, { target: { value: "א".repeat(501) } });
    fireEvent.click(forward());

    expect(screen.getByText(i18n.t("booking.notesTooLong"))).toBeInTheDocument();
    expect(createBooking).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/book/details");

    fireEvent.change(notes, { target: { value: "א".repeat(500) } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms");
  });

  it("never disables the forward control and moves focus to the first failure", async () => {
    await walkToDetails();

    const notes = screen.getByLabelText(i18n.t("booking.notes"));
    fireEvent.change(notes, { target: { value: "א".repeat(501) } });
    fireEvent.click(forward());

    // R7: it submits and fails visibly rather than stating no reason.
    expect(forward()).toBeEnabled();
    expect(screen.getByText(i18n.t("booking.nameRequired"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("booking.notesTooLong"))).toBeInTheDocument();
    // Name is first in the form, so it is first in focus order.
    expect(document.activeElement).toBe(screen.getByLabelText(i18n.t("booking.name")));

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(document.activeElement).toBe(notes);
  });
});

describe("BookPage details step — the bound dress", () => {
  it("names the binding and offers every size as a radio", async () => {
    await walkToDetails("d1");

    expect(
      await screen.findByText(i18n.t("booking.forDress", { dress: "שמלת אלמה" })),
    ).toBeInTheDocument();
    expect(screen.getByText(i18n.t("dress.sizes"))).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /^36/ })).toBeInTheDocument();
    expect(getDress).toHaveBeenCalledWith("d1");
  });

  it("keeps an unavailable size selectable and names it inside that chip", async () => {
    await walkToDetails("d1");

    const unavailable = await screen.findByRole("radio", { name: /38/ });
    // D4 + R15: the word is part of THIS radio's accessible name, not a
    // group-level sentence a screen reader never ties to the chip.
    expect(unavailable).toBeEnabled();
    expect(unavailable).toHaveAccessibleName(
      new RegExp(`38.*${i18n.t("booking.sizeUnavailable")}`, "s"),
    );
    fireEvent.click(unavailable);
    expect(unavailable).toBeChecked();

    // The longer invitation is one muted sentence under the group.
    expect(screen.getByText(i18n.t("booking.sizeUnavailableNote"))).toBeInTheDocument();
  });

  it("drops the note when every size is in the boutique", async () => {
    getDress.mockResolvedValue(
      dressDetail({ sizes: [{ size_label: "36", available: true }] }),
    );

    await walkToDetails("d1");

    await screen.findByRole("radio", { name: /^36/ });
    expect(screen.queryByText(i18n.t("booking.sizeUnavailableNote"))).toBeNull();
  });

  it("refuses to advance without a size whenever a dress is bound", async () => {
    await walkToDetails("d1");

    const size = await screen.findByRole("radio", { name: /^36/ });
    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());

    // dress_id without dress_size is a 400 at the boundary — the two are a pair.
    expect(screen.getByText(i18n.t("booking.sizeRequired"))).toHaveAttribute("role", "alert");
    expect(document.activeElement).toBe(size);
    expect(createBooking).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/book/details/d1");

    fireEvent.click(size);
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms/d1");
  });

  it("marks every size radio required", async () => {
    await walkToDetails("d1");

    for (const radio of await screen.findAllByRole("radio")) {
      expect(radio).toBeRequired();
    }
  });

  it("lets her type her name while the dress read is still in flight", async () => {
    getDress.mockReturnValue(pending());

    const { container } = await walkToDetails("d1");

    // The form is never blocked on a decoration.
    const name = screen.getByLabelText(i18n.t("booking.name"));
    fireEvent.change(name, { target: { value: "נועה" } });
    expect(name).toHaveValue("נועה");
    expect(container.querySelectorAll(".animate-skeleton").length).toBeGreaterThan(0);
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("drops the binding on a 404 and continues as a generic appointment", async () => {
    getDress.mockRejectedValue(GONE);

    await walkToDetails("d1");

    expect(await screen.findByText(i18n.t("booking.dressGoneGeneric"))).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.queryByText(i18n.t("dress.sizes"))).toBeNull();
    expect(screen.queryByText(/שמלת אלמה/)).toBeNull();

    // No size to pick, so no size is required: the generic path is a complete
    // booking, never a dead end.
    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms/d1");
  });

  it("drops the binding when the dress has no active sizes, keeping it on screen", async () => {
    getDress.mockResolvedValue(dressDetail({ sizes: [] }));

    await walkToDetails("d1");

    // Nothing failed and nothing vanished — polite, not an alert.
    const note = await screen.findByText(i18n.t("booking.dressGoneGeneric"));
    expect(note).toHaveAttribute("role", "status");
    expect(
      screen.getByText(i18n.t("booking.forDress", { dress: "שמלת אלמה" })),
    ).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("dress.sizes"))).toBeNull();

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(forward());
    expect(window.location.pathname).toBe("/book/terms/d1");
  });

  it("drops the binding on a non-404 failure with no retry and no error voice", async () => {
    getDress.mockRejectedValue(DOWN);

    await walkToDetails("d1");

    expect(await screen.findByText(i18n.t("booking.dressGoneGeneric"))).toBeInTheDocument();
    // A 5xx on a decoration must not stop a bride booking a fitting.
    expect(screen.queryByRole("button", { name: i18n.t("catalog.retry") })).toBeNull();
    expect(screen.queryByText(i18n.t("errors.unknown"))).toBeNull();
    expect(forward()).toBeEnabled();
  });
});

describe("BookPage terms step", () => {
  it("states the two refund numbers above the policy, in plain Hebrew", async () => {
    await walkToTerms();

    const window_ = screen.getByText(i18n.t("booking.refundWindow", { hours: 48 }));
    const forfeit = screen.getByText(i18n.t("booking.forfeit", { percent: 50 }));
    const policy = screen.getByText(TERMS.terms_text);

    // A paragraph is where numbers go to hide, so they sit above it.
    expect(window_.compareDocumentPosition(policy)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(forfeit.compareDocumentPosition(policy)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders the policy as text, never as HTML", async () => {
    getTerms.mockResolvedValue({ ...TERMS, terms_text: "שורה\n<b>לא תגית</b>" });

    const { container } = await walkToTerms();

    // A public, anonymous, multi-tenant surface: any HTML path here is stored
    // XSS reachable by every visitor to that tenant's storefront.
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText(/<b>לא תגית<\/b>/)).toBeInTheDocument();
  });

  it("grows the page instead of boxing the policy in its own scroller", async () => {
    await walkToTerms();

    const policy = screen.getByText(TERMS.terms_text);
    // pre-line keeps the owner's line breaks; two scroll contexts on a 375
    // phone is a trap, and a keyboard-scrollable box is a tab stop between the
    // text and the consent.
    expect(policy.className).toContain("whitespace-pre-line");
    expect(policy).toHaveAttribute("dir", "auto");
    expect(policy.className).not.toMatch(/overflow-(x|y|auto|scroll)|max-h-/);
    expect(policy).not.toHaveAttribute("tabindex");
  });

  it("refuses to advance without consent and moves focus to the checkbox", async () => {
    await walkToTerms();

    fireEvent.click(forward());

    expect(screen.getByText(i18n.t("booking.acceptRequired"))).toHaveAttribute("role", "alert");
    const consent = screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") });
    expect(document.activeElement).toBe(consent);
    expect(consent).toHaveAttribute("aria-invalid", "true");
    // A disabled forward button on a legal-consent screen states no reason.
    expect(forward()).toBeEnabled();
    expect(window.location.pathname).toBe("/book/terms");
  });

  it("advances to the verify step once consent is given", async () => {
    await walkToTerms();

    fireEvent.click(screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }));
    fireEvent.click(forward());

    expect(window.location.pathname).toBe("/book/verify");
  });

  it("ties the consent to the version it was given for", async () => {
    await walkToTerms();

    const consent = screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") });
    fireEvent.click(consent);
    expect(consent).toBeChecked();

    // Walking back and forward is the same version, so it survives — the reset
    // is keyed on the version, which is what TERMS_STALE replaces.
    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));
    expect(window.location.pathname).toBe("/book/details");
    fireEvent.click(forward());
    expect(
      screen.getByRole("checkbox", { name: i18n.t("booking.acceptTerms") }),
    ).toBeChecked();
  });
});

describe("BookPage — step guards and the back control", () => {
  it("returns a later step entered with no picked slot to the slot step", async () => {
    renderFlow("/book/terms");

    expect(window.location.pathname).toBe("/book/slot");
    expect(await screen.findByRole("radio", { name: /מדידה ראשונה/ })).toBeInTheDocument();
  });

  it("keeps the bound dress on the way back to the slot step", () => {
    renderFlow("/book/details/d1");

    expect(window.location.pathname).toBe("/book/slot/d1");
  });

  it("exempts confirm from the guard — the booking is already written", () => {
    renderFlow("/book/confirm");

    expect(window.location.pathname).toBe("/book/confirm");
  });

  it("walks back one step at a time with a Link, never the history stack", async () => {
    await walkToDetails("d 1");

    const back = screen.getByRole("link", { name: i18n.t("booking.backStep") });
    expect(back).toHaveAttribute("href", "/book/slot/d%201");

    fireEvent.change(screen.getByLabelText(i18n.t("booking.name")), { target: { value: "נועה" } });
    fireEvent.click(await screen.findByRole("radio", { name: /^36/ }));
    fireEvent.click(forward());

    expect(screen.getByRole("link", { name: i18n.t("booking.backStep") })).toHaveAttribute(
      "href",
      "/book/details/d%201",
    );
  });

  it("keeps the picked slot when she walks back to it", async () => {
    await walkToDetails();

    fireEvent.click(screen.getByRole("link", { name: i18n.t("booking.backStep") }));

    expect(window.location.pathname).toBe("/book/slot");
    expect(screen.getByRole("radio", { name: "10:00" })).toBeChecked();
  });
});
