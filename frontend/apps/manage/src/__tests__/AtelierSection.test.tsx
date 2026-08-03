import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { AtelierBoardResponse, AtelierTicket } from "../api";
import { AtelierSection } from "../components/AtelierSection";
import { IDLE_STOP_MS, POLL_INTERVAL_MS } from "../lib/usePoll";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      getAtelierBoard: vi.fn(),
      createTicket: vi.fn(),
      updateTicket: vi.fn(),
      assignTicket: vi.fn(),
      advanceStage: vi.fn(),
      undoStage: vi.fn(),
      deleteTicket: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getAtelierBoard = vi.mocked(api.getAtelierBoard);
const advanceStage = vi.mocked(api.advanceStage);
const undoStage = vi.mocked(api.undoStage);
const assignTicket = vi.mocked(api.assignTicket);
const createTicket = vi.mocked(api.createTicket);
const updateTicket = vi.mocked(api.updateTicket);
const deleteTicket = vi.mocked(api.deleteTicket);

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3) and 07:07 in New York — and the test
// script pins TZ=America/New_York, so an unzoned read prints 07:07 and every
// time assertion below fails loudly rather than quietly.
const NOW = "2026-08-04T11:07:00Z";

const OWNER_ID = "11111111-1111-1111-1111-111111111111";
const NOA_ID = "22222222-2222-2222-2222-222222222222";
const OTHER_SEAMSTRESS = "33333333-3333-3333-3333-333333333333";
const T1 = "aaaaaaaa-0000-0000-0000-000000000001";
const T2 = "aaaaaaaa-0000-0000-0000-000000000002";

function ticket(overrides: Partial<AtelierTicket> = {}): AtelierTicket {
  return {
    id: T1,
    customer_name: "מיכל לוי",
    due_date: "2026-08-12",
    overdue: false,
    effort_minutes: 120,
    assigned_staff_user_id: null,
    dress_id: null,
    dress_name: "ולנטינה",
    dress_size: "38",
    notes: "להרים 4 ס״מ, לצרף חגורה",
    stage: "intake",
    intake_at: "2026-08-01T08:00:00Z",
    in_progress_at: null,
    qc_at: null,
    ready_at: null,
    delivered_at: null,
    ...overrides,
  };
}

const BANDS = [
  { band: "thirty_min", minutes: 30 },
  { band: "one_hour", minutes: 60 },
  { band: "two_hours", minutes: 120 },
  { band: "half_day", minutes: 240 },
  { band: "full_day", minutes: 480 },
] as const;

function board(
  tickets: AtelierTicket[],
  overrides: Partial<AtelierBoardResponse> = {},
): AtelierBoardResponse {
  return {
    tickets,
    seamstresses: [{ id: NOA_ID, display_name: "נועה לוי", assignable: true }],
    effort_bands: BANDS.map((entry) => ({ ...entry })),
    truncated: false,
    ...overrides,
  };
}

// AtelierSection renders inside ConsoleShell's <main>, which owns the console's
// single sr-only <h1>. The axe harness reproduces that frame rather than scanning
// a headless fragment whose heading order starts at h2.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

function mount(props: { selfId?: string; role?: string } = {}) {
  return render(<AtelierSection selfId={props.selfId ?? OWNER_ID} role={props.role ?? "owner"} />);
}

// Both Modals mount at SECTION level and are always in the tree, so a dialog is
// addressed by its TITLE and its openness is read off the element.
function openDialog(title: string): HTMLElement {
  const dialog = screen.getByRole("dialog", { hidden: true, name: title });
  expect((dialog as HTMLDialogElement).open).toBe(true);
  return dialog;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getAtelierBoard.mockReset();
  advanceStage.mockReset();
  undoStage.mockReset();
  assignTicket.mockReset();
  createTicket.mockReset();
  updateTicket.mockReset();
  deleteTicket.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

async function advanceTimers(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

// ⚠ `act`, and deliberately not a bare click followed by `waitFor`. RTL's
// `waitFor` ADVANCES FAKE TIMERS, so it fires poll ticks inside the window a
// mutation assertion is measuring — and a tick whose mocked payload is the
// PRE-mutation board drags the card back to where it started. `act` flushes
// React and the promise chain and nothing else.
async function clickAndSettle(node: HTMLElement) {
  await act(async () => {
    fireEvent.click(node);
  });
}

const STAGE_WORDS = ["התקבל", "בעבודה", "בקרה", "מוכן", "נמסר"] as const;

// --- §9.1: five named regions of five named lists ---------------------------

describe("the board's structure", () => {
  it("resolves each of the five columns as a NAMED list", async () => {
    // An unnamed <ul> is an anonymous list: a user navigating by list (NVDA `L`,
    // VoiceOver rotor) would land on five consecutive anonymous lists with no
    // way to tell `qc` from `ready`.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    for (const word of STAGE_WORDS) {
      expect(screen.getByRole("list", { name: word })).toBeInTheDocument();
    }
  });

  it("exposes each column as a NAMED region, which a CSS-grid <div> would not be", async () => {
    // An unnamed <section> is not exposed as a region AT ALL — so this assertion
    // also catches a column rendered as a <div> when someone reaches for grid.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const regions = screen.getAllByRole("region");
    expect(regions).toHaveLength(5);
    regions.forEach((region, index) => {
      expect(region.getAttribute("aria-labelledby")).not.toBeNull();
      expect(region).toHaveTextContent(STAGE_WORDS[index]);
    });
  });

  it("puts the stage word and the count in the <h3>, with NO noun", async () => {
    // Hebrew has singular, dual and plural agreement, so «{{total}} כרטיסים» is
    // wrong at 1 and at 2; the <ul>'s own list role already announces the count.
    getAtelierBoard.mockResolvedValue(
      board([ticket(), ticket({ id: T2, customer_name: "רותם כהן" })]),
    );
    mount();
    await screen.findByText("מיכל לוי");

    const intake = screen.getAllByRole("heading", { level: 3 })[0];
    expect(intake).toHaveTextContent("התקבל · 2");
    expect(intake.textContent).not.toContain("כרטיס");
  });

  it("gives every column <ul> a tab stop, unconditionally at every width", async () => {
    // A bounded `overflow-y: auto` container must be keyboard reachable (axe's
    // scrollable-region-focusable). ⚠ jsdom has no layout engine, so axe cannot
    // see the overflow and the attribute is asserted directly — the alternative
    // is a resize observer deciding an ARIA-relevant attribute.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    for (const word of STAGE_WORDS) {
      expect(screen.getByRole("list", { name: word })).toHaveAttribute("tabindex", "0");
    }
  });

  it("renders one h2 and five h3 — and the CARD carries no heading", async () => {
    // Sixty headings between two columns is what a per-card heading buys.
    getAtelierBoard.mockResolvedValue(
      board([ticket(), ticket({ id: T2, customer_name: "רותם כהן" })]),
    );
    mount();
    await screen.findByText("רותם כהן");

    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(5);
    expect(screen.queryAllByRole("heading", { level: 4 })).toHaveLength(0);
  });

  it("orders the columns in stage order and never re-sorts the server's tickets", async () => {
    getAtelierBoard.mockResolvedValue(
      board([
        ticket({ id: T1, customer_name: "מיכל לוי", due_date: "2026-08-20" }),
        ticket({ id: T2, customer_name: "רותם כהן", due_date: "2026-08-01" }),
      ]),
    );
    mount();
    await screen.findByText("מיכל לוי");

    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent ?? "");
    STAGE_WORDS.forEach((word, index) => expect(headings[index]).toContain(word));

    // Server order, verbatim: due_date ASC is the bride-date rank the epic
    // subtracts from, and a second client-side sort is a second thing to agree.
    const names = within(screen.getByRole("list", { name: "התקבל" }))
      .getAllByRole("listitem")
      .map((li) => li.textContent ?? "");
    expect(names[0]).toContain("מיכל לוי");
    expect(names[1]).toContain("רותם כהן");
  });
});

// --- §1.1: the stage rail ----------------------------------------------------

describe("the stage rail", () => {
  it("is a NAMED second navigation landmark carrying five links in stage order", async () => {
    // A second navigation landmark beside the shell's must be named or a
    // screen-reader user cycling landmarks lands on two things both called
    // "navigation".
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const rail = screen.getByRole("navigation", { name: "מעבר לשלב" });
    const chips = within(rail).getAllByRole("link");
    expect(chips).toHaveLength(5);
    STAGE_WORDS.forEach((word, index) => expect(chips[index]).toHaveTextContent(word));
  });

  it("points every chip at a column heading that carries tabIndex={-1}", async () => {
    // ⚠ Fragment navigation to a tabindex="-1" target focuses it — which is how
    // ConsoleShell's shipped SkipLink reaches #console-main, so the rail needs
    // no focus code and no scrollIntoView. jsdom does NOT implement fragment
    // navigation, so what is asserted is the WIRING: the href, the id it names
    // and the -1 that makes the target focusable.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    const { container } = mount();
    await screen.findByText("מיכל לוי");

    const chips = within(screen.getByRole("navigation", { name: "מעבר לשלב" })).getAllByRole(
      "link",
    );
    for (const chip of chips) {
      const href = chip.getAttribute("href") ?? "";
      expect(href.startsWith("#atelier-h-")).toBe(true);
      const target = container.querySelector(href.replace("#", "#"));
      expect(target).not.toBeNull();
      expect(target).toHaveAttribute("tabindex", "-1");
      expect(target?.tagName).toBe("H3");
    }
  });

  it("renders a chip for an EMPTY column reading «· 0» and still links it", async () => {
    // A chip that vanishes is a control that moves under a finger, and the
    // pipeline is five stages whether or not a boutique is using all five today.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const rail = screen.getByRole("navigation", { name: "מעבר לשלב" });
    expect(within(rail).getByRole("link", { name: /בקרה · 0/ })).toHaveAttribute(
      "href",
      "#atelier-h-qc",
    );
  });

  it("carries the 44px floor on every chip — `py-2 text-sm` lands near 40", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    for (const chip of within(
      screen.getByRole("navigation", { name: "מעבר לשלב" }),
    ).getAllByRole("link")) {
      expect(chip).toHaveClass("min-h-11");
    }
  });
});

// --- §9.4: SC 2.2.2, the row no tool will ever add for us --------------------

describe("SC 2.2.2 — the sole automated coverage, because axe has NO rule for it", () => {
  it("stops the loop on pause, announces once, and keeps focus on the control", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "השהיה — לוח התפירה" });
    control.focus();
    fireEvent.click(control);

    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("העדכון מושהה.");
    // ONE button whose NAME changes — never two, never aria-pressed.
    const resumed = screen.getByRole("button", { name: "חידוש — לוח התפירה" });
    expect(resumed).toHaveTextContent("חידוש");
    expect(resumed).not.toHaveAttribute("aria-pressed");
    // It renamed, it did not unmount, so focus is still on it.
    expect(document.activeElement).toBe(resumed);

    const before = getAtelierBoard.mock.calls.length;
    await advanceTimers(POLL_INTERVAL_MS * 4);
    expect(getAtelierBoard).toHaveBeenCalledTimes(before);
  });

  it("fetches immediately on resume, at the BASE gap and not a backed-off one", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "השהיה — לוח התפירה" }));
    const paused = getAtelierBoard.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "חידוש — לוח התפירה" }));
    await waitFor(() => expect(getAtelierBoard.mock.calls.length).toBe(paused + 1));
    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("העדכון חודש.");

    // …and the next beat is the BASE interval, not a doubled one.
    await advanceTimers(POLL_INTERVAL_MS);
    await waitFor(() => expect(getAtelierBoard.mock.calls.length).toBe(paused + 2));
  });

  it("is the FIRST focusable thing inside the section, before any card", async () => {
    // A 2.2.2 mechanism placed after the content it governs is reachable only by
    // walking the list that is repainting under the walk.
    getAtelierBoard.mockResolvedValue(
      board([ticket(), ticket({ id: T2, customer_name: "רותם כהן" })]),
    );
    const { container } = mount();
    await screen.findByText("רותם כהן");

    expect(Array.from(container.querySelectorAll("button"))[0]).toHaveAccessibleName(
      "השהיה — לוח התפירה",
    );
  });

  it("renders the control at the 44px floor — a class, never a measurement", async () => {
    // jsdom has no layout engine, so a measured assertion here would be a lie.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getByRole("button", { name: "השהיה — לוח התפירה" })).toHaveClass("min-h-11");
  });

  it("fires the idle stop, names its CAUSE and names its own REGION", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    await advanceTimers(IDLE_STOP_MS);

    const cue = screen.getByTestId("atelier-cue");
    expect(cue).toHaveTextContent("עדכון לוח התפירה הופסק");
    // ⚠ Named region: all three of the console's polling surfaces write into a
    // role="status" and all three idle windows are reset by the same global
    // listeners, so a sentence that named no region names nothing.
    expect(cue).toHaveTextContent("לוח התפירה");
    expect(screen.getByRole("button", { name: "חידוש — לוח התפירה" })).toBeInTheDocument();
  });

  it("shows NO pause control over a skeleton", async () => {
    // Nothing is auto-updating yet, so a control here pauses a fetch the user
    // has not seen produce anything.
    getAtelierBoard.mockReturnValue(new Promise(() => {}));
    mount();

    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("טוען את לוח התפירה…");
    expect(screen.queryByRole("button", { name: /השהיה/ })).toBeNull();
  });
});

// --- §4.2: the live region under a five-second poll -------------------------

describe("the announced region", () => {
  it("does NOT change across THREE consecutive ticks with the cue already populated", async () => {
    // ⚠ F34's F-7, and the reason the cue must be POPULATED first: a single-tick
    // assertion passes against the broken version whenever the cue starts empty.
    // Assigning a non-empty string to a text node runs the DOM's
    // string-replace-all and produces a real childList mutation EVEN WHEN THE
    // TWO STRINGS ARE BYTE-IDENTICAL.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockResolvedValue(
      ticket({ stage: "in_progress", in_progress_at: "2026-08-04T11:00:00Z" }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByTestId("atelier-cue")).toHaveTextContent("שלב חדש"),
    );

    const cue = screen.getByTestId("atelier-cue");
    const records: MutationRecord[] = [];
    const observer = new MutationObserver((list) => records.push(...list));
    observer.observe(cue, { childList: true, characterData: true, subtree: true });

    const before = getAtelierBoard.mock.calls.length;
    await advanceTimers(POLL_INTERVAL_MS);
    await advanceTimers(POLL_INTERVAL_MS);
    await advanceTimers(POLL_INTERVAL_MS);

    // Both halves: the ticks HAPPENED, and they wrote nothing.
    expect(getAtelierBoard.mock.calls.length).toBeGreaterThanOrEqual(before + 3);
    expect(records.concat(observer.takeRecords())).toEqual([]);
    observer.disconnect();
  });

  it("names the bride AND the destination stage on an advance", async () => {
    // ⚠ For a sighted user the move is self-evident — the card is visibly in
    // another column. FOR A SCREEN-READER USER THIS SENTENCE IS THE MOVE, which
    // is why its textContent is asserted and not merely that it changed.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    advanceStage.mockResolvedValue(ticket({ stage: "qc" }));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));

    await waitFor(() => {
      const cue = screen.getByTestId("atelier-cue");
      expect(cue).toHaveTextContent("מיכל לוי");
      expect(cue).toHaveTextContent("בקרה");
    });
  });

  it("renders an interpolated bride's name in a BARE <bdi>", async () => {
    // dir="ltr" on «מיכל לוי» reverses its words — a bidi defect that looks
    // deliberate, which is the kind nobody files.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    advanceStage.mockResolvedValue(ticket({ stage: "qc" }));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByTestId("atelier-cue")).toHaveTextContent("מיכל לוי"),
    );

    const bdi = screen.getByTestId("atelier-cue").querySelector("bdi");
    expect(bdi).toHaveTextContent("מיכל לוי");
    expect(bdi).not.toHaveAttribute("dir");
  });

  it("changes on a pause", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("");
    fireEvent.click(screen.getByRole("button", { name: "השהיה — לוח התפירה" }));
    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("העדכון מושהה.");
  });

  it("puts no live attributes on the five lists", async () => {
    // role="log" is the tempting wrong answer — it is for append-only chat, and
    // these lists mutate in place and hand items to each other.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    for (const word of STAGE_WORDS) {
      const list = screen.getByRole("list", { name: word });
      expect(list).not.toHaveAttribute("aria-live");
      expect(list.getAttribute("role")).toBeNull();
    }
  });

  it("keeps the freshness line OUTSIDE every announced region and never aria-hidden", async () => {
    // aria-hidden would make the board's only honesty signal sighted-only.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const freshness = screen.getByText(/עודכן/);
    expect(freshness.closest('[role="status"]')).toBeNull();
    expect(freshness.closest('[role="alert"]')).toBeNull();
    expect(freshness.closest("[aria-live]")).toBeNull();
    expect(freshness.closest("[aria-hidden]")).toBeNull();
  });

  it("NEGATIVE CONTROL: role=status DOES match when nested, and [aria-live] never does", () => {
    // ⚠ Without this fixture the assertion above is three selectors of which one
    // is VACUOUS: every live region in this repo is a bare role="status" with no
    // aria-live attribute, and closest() matches ATTRIBUTES, not implicit ARIA —
    // so closest('[aria-live]') returns null even nested inside the region.
    render(
      <p role="status">
        <span>עודכן 14:07</span>
      </p>,
    );
    const inside = screen.getByText("עודכן 14:07");

    expect(inside.closest('[role="status"]')).not.toBeNull();
    expect(inside.closest("[aria-live]")).toBeNull();
  });
});

// --- §5: the board states ----------------------------------------------------

describe("the board states", () => {
  it("A-load: one skeleton Card, no rail, no freshness row, and the cue announces", async () => {
    getAtelierBoard.mockReturnValue(new Promise(() => {}));
    mount();

    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("טוען את לוח התפירה…");
    expect(screen.queryByRole("navigation", { name: "מעבר לשלב" })).toBeNull();
    expect(screen.queryByText(/עודכן/)).toBeNull();
  });

  it("A: the freshness claim is zoned to Jerusalem and changes only on a success", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    // 14:07 Jerusalem, NOT 11:07 UTC and not 07:07 New York.
    expect(screen.getByText(/עודכן/)).toHaveTextContent("14:07");
  });

  it("A-empty: one EmptyState teaching the five stage words, and NO columns and NO rail", async () => {
    // ⚠ The first thing every new boutique sees. Five columns each reading «אין
    // כרטיסים בשלב זה» is a wall of nothing that looks broken.
    getAtelierBoard.mockResolvedValue(board([]));
    mount();
    await screen.findByText("אין עדיין כרטיסי תפירה");

    expect(screen.queryAllByRole("region")).toHaveLength(0);
    expect(screen.queryByRole("navigation", { name: "מעבר לשלב" })).toBeNull();
    const body = screen.getByText(/כל כרטיס עובר חמישה שלבים/);
    for (const word of STAGE_WORDS) {
      expect(body).toHaveTextContent(word);
    }
    // The CTA rides the EmptyState's own `action`, and the freshness row still
    // renders: a surface that has stopped updating must still be able to say so.
    expect(screen.getByRole("button", { name: "כרטיס חדש" })).toBeInTheDocument();
    expect(screen.getByText(/עודכן/)).toBeInTheDocument();
  });

  it("A-emptycol: a muted line INSIDE the column, with the other four as context", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getAllByText("אין כרטיסים בשלב זה")).toHaveLength(4);
  });

  it("A-fail: the OUTAGE register plus «רענון» — and the pause control DOES render", async () => {
    // The loop is alive and backing off, so a viewer who wants it stopped must
    // be able to stop it.
    getAtelierBoard.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    mount();

    await screen.findByText("לא הצלחנו לטעון את לוח התפירה כרגע.");
    expect(screen.getByRole("button", { name: "רענון" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "השהיה — לוח התפירה" })).toBeInTheDocument();
  });

  it("A-stale: THE CARDS STAY, the claim escalates, and nothing states an interval", async () => {
    // The backoff falsifies any number the moment it doubles.
    getAtelierBoard.mockResolvedValueOnce(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    getAtelierBoard.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    await advanceTimers(POLL_INTERVAL_MS);

    await waitFor(() => expect(screen.getByText(/אין עדכון מאז/)).toBeInTheDocument());
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
    expect(screen.getByText("ייתכן שהמידע אינו עדכני.")).toBeInTheDocument();
    expect(screen.getByText(/אין עדכון מאז/)).toHaveClass("font-semibold", "text-warning-text");
    expect(screen.getByRole("button", { name: "רענון" })).toBeInTheDocument();
  });

  it("A-paused: the cards stay, are NOT dimmed, and «רענון» is absent", async () => {
    // They were correct at «עודכן 14:07» and pausing did not make them wrong —
    // and «רענון» beside «חידוש» is two Hebrew words a hurried reader will not
    // tell apart.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "השהיה — לוח התפירה" }));

    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
    expect(screen.getByText(/מושהה · עודכן/)).toBeInTheDocument();
    // The sentence is BOTH announced and displayed — the cue speaks it once and
    // the body line under the freshness claim is what a sighted user reads back
    // ten minutes later. Asserted as two elements so neither can quietly vanish.
    expect(screen.getByTestId("atelier-cue")).toHaveTextContent(
      "העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש.",
    );
    expect(
      screen
        .getAllByText("העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש.")
        .filter((node) => node.getAttribute("data-testid") !== "atelier-cue"),
    ).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "רענון" })).toBeNull();
  });

  it("A-idle: mechanically identical to A-paused, and ONE thing differs — the cause", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    await advanceTimers(IDLE_STOP_MS);

    expect(screen.getByText(/מושהה · עודכן/)).toBeInTheDocument();
    expect(
      screen
        .getAllByText(/עדכון לוח התפירה הופסק אחרי/)
        .filter((node) => node.getAttribute("data-testid") !== "atelier-cue"),
    ).toHaveLength(1);
    // ⚠ THE ONE THING THAT DIFFERS, and it is why there are two states: a board
    // that stopped by itself and does not say why is indistinguishable from a
    // board that broke.
    expect(screen.queryByText("העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש.")).toBeNull();
    expect(screen.queryByRole("button", { name: "רענון" })).toBeNull();
  });

  it("A-401: the loop stops, the cards are CLEARED and a reload affordance renders", async () => {
    getAtelierBoard.mockResolvedValueOnce(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    getAtelierBoard.mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "gone"));
    await advanceTimers(POLL_INTERVAL_MS);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("תוקף החיבור פג."),
    );
    // A dead session cannot vouch for the cards.
    expect(screen.queryByText("מיכל לוי")).toBeNull();
    expect(screen.getByRole("button", { name: "רענון הדף" })).toBeInTheDocument();
  });

  it("A-403: the same shape, a different sentence, and it NAMES NO ROLE", async () => {
    // The server ships ONE 403 body for every unadmitted role so a probe cannot
    // learn which roles exist.
    getAtelierBoard.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "no"));
    mount();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("אין הרשאה לצפות בלוח התפירה כרגע.");
    expect(alert.textContent).not.toContain("תופרת");
    expect(alert.textContent).not.toContain("אחראית");
    expect(screen.getByRole("button", { name: "רענון הדף" })).toBeInTheDocument();
  });

  it("A-trunc: says what was cut and NEVER states the number", async () => {
    // BOARD_TICKET_LIMIT is server-only and `truncated` is on the wire precisely
    // so the console never has to know it — a client that quoted 500 would be
    // one constant away from lying.
    getAtelierBoard.mockResolvedValue(board([ticket()], { truncated: true }));
    mount();
    await screen.findByText("מיכל לוי");

    const line = screen.getByText(/מוצגים הכרטיסים הדחופים ביותר/);
    expect(line).toBeInTheDocument();
    expect(line.textContent).not.toMatch(/\d/);
  });

  it("A-trunc is absent when the flag is false", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.queryByText(/מוצגים הכרטיסים הדחופים ביותר/)).toBeNull();
  });

  it("A-busy: only the tapped control is disabled; the rest of the board stays live", async () => {
    getAtelierBoard.mockResolvedValue(
      board([ticket(), ticket({ id: T2, customer_name: "רותם כהן" })]),
    );
    advanceStage.mockReturnValue(new Promise(() => {}));
    mount();
    await screen.findByText("מיכל לוי");

    const controls = screen.getAllByRole("button", { name: /לשלב הבא/ });
    fireEvent.click(controls[0]);

    await waitFor(() => expect(controls[0]).toBeDisabled());
    expect(controls[1]).not.toBeDisabled();
  });

  it("A-ok: the card is patched FROM THE RESPONSE and moves column", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockResolvedValue(
      ticket({ stage: "in_progress", in_progress_at: "2026-08-04T11:00:00Z" }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    await clickAndSettle(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));

    expect(
      within(screen.getByRole("list", { name: "בעבודה" })).getByText("מיכל לוי"),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 })[1]).toHaveTextContent("בעבודה · 1");
    expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent("התקבל · 0");
  });

  it("suppresses every tick while a mutation is in flight", async () => {
    // The reachable path is the VISIBILITYCHANGE refetch, not the timer: the
    // mutation calls poll.clearTick() so no timer is armed, which is why a
    // timer-only assertion here would be vacuous.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockReturnValue(new Promise(() => {}));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() => expect(advanceStage).toHaveBeenCalled());
    const before = getAtelierBoard.mock.calls.length;

    await act(async () => {
      Object.defineProperty(document, "hidden", { configurable: true, value: true });
      document.dispatchEvent(new Event("visibilitychange"));
      Object.defineProperty(document, "hidden", { configurable: true, value: false });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(getAtelierBoard).toHaveBeenCalledTimes(before);
    await advanceTimers(POLL_INTERVAL_MS * 3);
    expect(getAtelierBoard).toHaveBeenCalledTimes(before);
  });

  it("holds the repaint while a pointer is down — a card moving column is a LAYOUT change", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const before = getAtelierBoard.mock.calls.length;
    await act(async () => {
      window.dispatchEvent(new Event("pointerdown"));
    });
    await advanceTimers(POLL_INTERVAL_MS);
    expect(getAtelierBoard).toHaveBeenCalledTimes(before);

    await act(async () => {
      window.dispatchEvent(new Event("pointerup"));
    });
    await advanceTimers(POLL_INTERVAL_MS);
    expect(getAtelierBoard.mock.calls.length).toBeGreaterThan(before);
  });
});

// --- §3.2: nothing on this board mutates on `change` -------------------------

describe("the select -> draft -> commit split (WCAG 3.2.2 On Input, Level A)", () => {
  it("`{ArrowDown}{ArrowDown}` on the skip Select calls api.advanceStage ZERO times", async () => {
    // ⚠ On Windows Chrome and Firefox a CLOSED native <select> changes its value
    // and fires `change` on EVERY arrow keypress — which is why two `change`
    // events are the faithful model here and user-event's keyboard is not (it
    // does not simulate it at all). A keyboard user on an `in_progress` card
    // arrowing to «נמסר» would otherwise fire three advances — three timestamps,
    // three audit rows, three column moves and three focus moves — before
    // committing to anything. Under the five-timestamp state machine those
    // stamps ARE the trail, and each needs its own undo call to reverse.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    advanceStage.mockResolvedValue(ticket({ stage: "ready" }));
    mount();
    await screen.findByText("מיכל לוי");

    const select = screen.getByRole("combobox", { name: "העברה לשלב — מיכל לוי" });
    fireEvent.change(select, { target: { value: "ready" } });
    fireEvent.change(select, { target: { value: "delivered" } });
    fireEvent.change(select, { target: { value: "ready" } });

    expect(advanceStage).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "העברה — מיכל לוי" }));
    await waitFor(() => expect(advanceStage).toHaveBeenCalledTimes(1));
    expect(advanceStage).toHaveBeenCalledWith(T1, "ready");
  });

  it("`{ArrowDown}{ArrowDown}` on the assign Select calls api.assignTicket ZERO times", async () => {
    // The named mutation must red BOTH pairs. If only one reds, the other select
    // was missed.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    assignTicket.mockResolvedValue(ticket({ assigned_staff_user_id: NOA_ID }));
    mount();
    await screen.findByText("מיכל לוי");

    const select = screen.getByRole("combobox", { name: "תופרת — מיכל לוי" });
    fireEvent.change(select, { target: { value: NOA_ID } });
    fireEvent.change(select, { target: { value: "" } });
    fireEvent.change(select, { target: { value: NOA_ID } });

    expect(assignTicket).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "שיוך — מיכל לוי" }));
    await waitFor(() => expect(assignTicket).toHaveBeenCalledTimes(1));
    expect(assignTicket).toHaveBeenCalledWith(T1, NOA_ID);
  });

  it("sends null to RELEASE through the elevated Select, as a value and not an omission", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket({ assigned_staff_user_id: NOA_ID })]));
    assignTicket.mockResolvedValue(ticket({ assigned_staff_user_id: null }));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.change(screen.getByRole("combobox", { name: "תופרת — מיכל לוי" }), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "שיוך — מיכל לוי" }));

    await waitFor(() => expect(assignTicket).toHaveBeenCalledWith(T1, null));
  });

  it("disables each commit Button until its sibling draft is set", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    mount();
    await screen.findByText("מיכל לוי");

    const commit = screen.getByRole("button", { name: "העברה — מיכל לוי" });
    expect(commit).toBeDisabled();
    fireEvent.change(screen.getByRole("combobox", { name: "העברה לשלב — מיכל לוי" }), {
      target: { value: "ready" },
    });
    expect(commit).not.toBeDisabled();
  });
});

// --- §2.3: the control matrix, asserted AS COSMETICS -------------------------

describe("which controls exist — the two authorization axes, rendered", () => {
  it("drops «לשלב הבא» on a delivered card", async () => {
    getAtelierBoard.mockResolvedValue(
      board([ticket({ stage: "delivered", delivered_at: "2026-08-03T09:00:00Z" })]),
    );
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.queryByRole("button", { name: /לשלב הבא/ })).toBeNull();
    expect(screen.getByRole("button", { name: "ביטול שלב — מיכל לוי" })).toBeInTheDocument();
  });

  it("renders the skip pair only when TWO OR MORE later stages exist", async () => {
    // With exactly one, the skip control offers what «לשלב הבא» already does,
    // and a board that offers one act twice has to be read twice.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "ready" })]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.queryByRole("combobox", { name: /העברה לשלב/ })).toBeNull();
    expect(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" })).toBeInTheDocument();
  });

  it("drops «ביטול שלב» at intake, because intake cannot be undone", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.queryByRole("button", { name: /ביטול שלב/ })).toBeNull();
  });

  it("gives an elevated user the assign Select and «שיוך», and a seamstress «לקחת»", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    const elevated = mount({ role: "shift_manager" });
    await screen.findByText("מיכל לוי");
    expect(screen.getByRole("combobox", { name: "תופרת — מיכל לוי" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /לקחת/ })).toBeNull();
    elevated.unmount();

    mount({ role: "seamstress", selfId: NOA_ID });
    await screen.findByText("מיכל לוי");
    expect(screen.queryByRole("combobox", { name: /תופרת/ })).toBeNull();
    expect(screen.getByRole("button", { name: "לקחת — מיכל לוי" })).toBeInTheDocument();
  });

  it("gives a seamstress «לשחרר» on her own ticket and «עריכה» with it", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket({ assigned_staff_user_id: NOA_ID })]));
    mount({ role: "seamstress", selfId: NOA_ID });
    await screen.findByText("מיכל לוי");

    expect(screen.getByRole("button", { name: "לשחרר — מיכל לוי" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "עריכה — מיכל לוי" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /מחיקה/ })).toBeNull();
  });

  it("refuses «עריכה» to a seamstress on an UNASSIGNED ticket she may still advance", async () => {
    // D3's per-verb asymmetry, rendered: she advances an unassigned ticket and
    // may not update one that is not hers.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount({ role: "seamstress", selfId: NOA_ID });
    await screen.findByText("מיכל לוי");

    expect(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /עריכה/ })).toBeNull();
  });

  it("shows a seamstress the FACTS and NO CONTROLS AT ALL on a colleague's ticket", async () => {
    // ⚠ No disabled buttons, no lock glyph, no «אין לך הרשאה» line. A disabled
    // control with no explanation is worse than an absent one; an explanation
    // would teach the permission model on a screen she opens fifty times a
    // shift; and either would be the client asserting a rule the server owns.
    getAtelierBoard.mockResolvedValue(
      board([ticket({ assigned_staff_user_id: NOA_ID })], {
        seamstresses: [
          { id: NOA_ID, display_name: "נועה לוי", assignable: true },
          { id: OTHER_SEAMSTRESS, display_name: "רותם", assignable: true },
        ],
      }),
    );
    mount({ role: "seamstress", selfId: OTHER_SEAMSTRESS });
    await screen.findByText("מיכל לוי");

    const card = screen.getByText("מיכל לוי").closest("li") as HTMLElement;
    expect(within(card).queryAllByRole("button")).toHaveLength(0);
    expect(within(card).queryAllByRole("combobox")).toHaveLength(0);
    // …and the facts are all still there.
    expect(within(card).getByText(/יעד/)).toBeInTheDocument();
    expect(within(card).getByText("להרים 4 ס״מ, לצרף חגורה")).toBeInTheDocument();
  });

  it("gives «מחיקה» to an elevated user only, as the screen's one danger control", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getByRole("button", { name: "מחיקה — מיכל לוי" })).toBeInTheDocument();
  });
});

// --- C8: target size, asserted as a CLASS ------------------------------------

describe("target size", () => {
  it("renders one control of each kind at the 44px floor", async () => {
    // Select.tsx declares NO min-height (`px-3 py-2 text-base` lands near 42),
    // so the class on both <select>s is not optional.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    mount();
    await screen.findByText("מיכל לוי");

    for (const name of [
      "לשלב הבא — מיכל לוי",
      "העברה — מיכל לוי",
      "שיוך — מיכל לוי",
      "ביטול שלב — מיכל לוי",
      "עריכה — מיכל לוי",
      "מחיקה — מיכל לוי",
    ]) {
      expect(screen.getByRole("button", { name })).toHaveClass("min-h-11");
    }
    for (const name of ["העברה לשלב — מיכל לוי", "תופרת — מיכל לוי"]) {
      expect(screen.getByRole("combobox", { name })).toHaveClass("min-h-11");
    }
  });

  it("carries no `size=\"sm\"` anywhere in the tree", async () => {
    // A card carrying up to seven controls in 295px is exactly the layout in
    // which someone reaches for `sm`. The answer is that the card is tall, not
    // that the targets are small — this console runs on staff phones.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    const { container } = mount();
    await screen.findByText("מיכל לוי");

    expect(container.querySelectorAll(".min-h-9")).toHaveLength(0);
  });
});

// --- §2.1 / §2.2 / §2.4: the card's facts ------------------------------------

describe("the card's facts", () => {
  it("never truncates, clips, ellipsises or line-clamps anything", async () => {
    // ⚠ `notes` is the one that LOOKS like it wants a clamp and is the one where
    // a clamp does the most damage: the note IS the work order, and «עריכה» is
    // refused to a seamstress on a ticket that is not hers — so a clamp would
    // hide the instruction from precisely the person doing the work.
    const long = "א".repeat(400);
    getAtelierBoard.mockResolvedValue(
      board([ticket({ notes: long, dress_name: "ולנטינה — גרסת ערב עם שובל ארוך במיוחד" })]),
    );
    const { container } = mount();
    await screen.findByText(long);

    expect(screen.getByText(long)).toBeInTheDocument();
    expect(screen.getByText(/ולנטינה — גרסת ערב/)).toBeInTheDocument();
    for (const banned of [".line-clamp-1", ".line-clamp-2", ".line-clamp-3", ".truncate"]) {
      expect(container.querySelectorAll(banned)).toHaveLength(0);
    }
    expect(screen.getByText(long).closest("p")).toHaveClass("break-words");
  });

  it("carries the WORD «באיחור» plus an escalated due line, and tints the card NOTHING", async () => {
    // Colour is never the signal. On a 60-card column a wall of red stops
    // meaning anything.
    getAtelierBoard.mockResolvedValue(board([ticket({ overdue: true })]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getByText("באיחור")).toBeInTheDocument();
    expect(screen.getByText(/יעד/)).toHaveClass("font-semibold", "text-danger");
    // The card itself gets NOTHING — the only danger boundary in the subtree is
    // the Badge's own border, which is reinforcement of a word that is already
    // there.
    const surface = screen.getByText("מיכל לוי").closest("li")?.firstElementChild as HTMLElement;
    expect(surface.className).not.toMatch(/danger/);
    expect(Array.from(surface.querySelectorAll(".border-danger"))).toEqual([
      screen.getByText("באיחור"),
    ]);
  });

  it("renders EXACTLY ONE Badge per card and never the stage", async () => {
    // The stage is the column heading; repeating it is 295px spent restating the
    // region plus a second place to keep true.
    getAtelierBoard.mockResolvedValue(board([ticket({ overdue: true, stage: "qc" })]));
    mount();
    await screen.findByText("מיכל לוי");

    const card = screen.getByText("מיכל לוי").closest("li") as HTMLElement;
    expect(within(card).getAllByText(/באיחור/)).toHaveLength(1);
    expect(card.textContent).not.toContain("בקרה");
  });

  it("carries NOTHING on an overdue DELIVERED ticket — it is history", async () => {
    getAtelierBoard.mockResolvedValue(
      board([ticket({ stage: "delivered", delivered_at: "2026-08-03T09:00:00Z", overdue: false })]),
    );
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.queryByText("באיחור")).toBeNull();
  });

  it("says «לא משויך» as muted words on an unassigned ticket", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    // ⚠ Scoped to the card: «לא משויך» is ALSO the release option in the
    // elevated assign Select, which is the same word doing the same job in two
    // places by design.
    const card = screen.getByText("מיכל לוי").closest("li") as HTMLElement;
    expect(within(card).getByText(/· לא משויך/)).toBeInTheDocument();
  });

  it("reads «תופרת שאינה פעילה» FROM THE WIRE'S FLAG, not from absence", async () => {
    // F51's staff CRUD can re-role or retire a seamstress and knows nothing
    // about this table, so the flag is what makes this a fact rather than an
    // inference — and it is the signal a manager needs to reassign.
    getAtelierBoard.mockResolvedValue(
      board([ticket({ assigned_staff_user_id: NOA_ID })], {
        seamstresses: [{ id: NOA_ID, display_name: "נועה לוי", assignable: false }],
      }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getByText(/תופרת שאינה פעילה/)).toBeInTheDocument();
    const card = screen.getByText("מיכל לוי").closest("li") as HTMLElement;
    expect(within(card).queryByText("נועה לוי")).toBeNull();
  });

  it("falls back to «{{minutes}} דק׳» when the stored minutes match no live band", async () => {
    // The visible consequence of "minutes persist, never the label": a boutique
    // that re-tuned «חצי יום» from 240 to 300 must not have older tickets
    // silently re-valued.
    getAtelierBoard.mockResolvedValue(board([ticket({ effort_minutes: 300 })]));
    mount();
    await screen.findByText("מיכל לוי");

    expect(screen.getByText(/300 דק׳/)).toBeInTheDocument();
  });

  it("omits the dress line entirely when both halves are null", async () => {
    // An alteration on the bride's own gown has no catalog row at all, so
    // absence is normal and is not rendered as an empty slot.
    getAtelierBoard.mockResolvedValue(board([ticket({ dress_name: null, dress_size: null })]));
    mount();
    await screen.findByText("מיכל לוי");

    const card = screen.getByText("מיכל לוי").closest("li") as HTMLElement;
    expect(within(card).queryByText("ולנטינה")).toBeNull();
    expect(card.textContent).not.toContain(" · 38");
  });
});

// --- C5: the error mapping ---------------------------------------------------

describe("a refused write", () => {
  it("names the two conflict codes and the 404 in their own sentences", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockRejectedValue(
      new ApiError(409, "TICKET_STAGE_CONFLICT", "ticket has moved on"),
    );
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("הכרטיס כבר התקדם."),
    );
    // A board-level error names no ticket, so the alert is INSIDE the card.
    expect(screen.getByRole("alert").closest("[data-ticket-id]")).not.toBeNull();
  });

  it("names a lost claim race in its own sentence, and does NOT name the winner", async () => {
    // The console does not have her name at the moment of the refusal, and the
    // next tick renders it on the card.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    assignTicket.mockRejectedValue(
      new ApiError(409, "TICKET_ALREADY_ASSIGNED", "claimed"),
    );
    mount({ role: "seamstress", selfId: NOA_ID });
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לקחת — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("הכרטיס כבר משויך."),
    );
    expect(screen.getByRole("alert").textContent).not.toContain("נועה");
  });

  it("treats a 404 as an in-card alert and NOT as terminal", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("הכרטיס כבר לא קיים."),
    );
    // A ticket vanishing is a fact about the ticket, not about her access.
    expect(screen.queryByText("אין הרשאה לצפות בלוח התפירה כרגע.")).toBeNull();
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
  });

  it("renders `atelier.error.rejected` for an UNMAPPED code and NEVER the response's message", async () => {
    // ⚠ THE STRUCTURAL GUARANTEE: main.py's *_BODY literals are ENGLISH, and
    // this console is Hebrew-only. A `default:` branch is what makes «no English
    // body can reach this console» true of every code F41 or a later feature
    // adds; a per-code map would leave the next new code uncovered.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "stage is not a valid TicketStage"),
    );
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("הפעולה נדחתה."),
    );
    expect(screen.getByRole("alert").textContent).not.toContain("stage is not a valid");
  });

  it("makes a write's 403 TERMINAL, on the same {401,403} rule the ticks use", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "no"));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("אין הרשאה לצפות בלוח התפירה כרגע."),
    );
  });
});

// --- §7: the intake / edit dialog -------------------------------------------

describe("the intake and edit dialog", () => {
  it("opens on «כרטיס חדש» with NO dress Select, an EMPTY due date and «שעה» selected", async () => {
    // ⚠ THE CATALOG PICKER IS CUT: the board payload carries no dresses, the
    // only source is a route gated owner + shift_manager while this dialog
    // admits a seamstress, and the card renders no image — so `dress_id` has no
    // reader on this surface. The free-text field ships alone.
    //
    // The due date defaults to EMPTY and never to today: it is the one field a
    // hurried user must not be able to accept by not looking at it.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");

    expect(within(dialog).queryByLabelText("שמלה")).toBeNull();
    expect(within(dialog).getByLabelText("שם השמלה")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("תאריך יעד")).toHaveValue("");
    expect(within(dialog).getByLabelText("הערכת זמן")).toHaveValue("one_hour");
    expect(within(dialog).getByLabelText("שם הלקוחה")).toHaveValue("");
  });

  it("labels every band option with the WORD AND its tenant-resolved minutes", async () => {
    // F41 ships no editor for the mapping and F42 owns it, so showing the number
    // at the moment the estimate is made is what lets an owner discover on day
    // one that the platform thinks her half-day is four hours. An <option> takes
    // no markup, so the numeric run is bracketed by Hebrew on both sides.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");

    const options = within(dialog)
      .getByLabelText("הערכת זמן")
      .querySelectorAll("option");
    expect(Array.from(options).map((option) => option.textContent)).toEqual([
      "חצי שעה · 30 דק׳",
      "שעה · 60 דק׳",
      "שעתיים · 120 דק׳",
      "חצי יום · 240 דק׳",
      "יום מלא · 480 דק׳",
    ]);
  });

  it("refuses an empty name, an unparseable phone and a missing due date before the request", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");
    fireEvent.change(within(dialog).getByLabelText("טלפון"), { target: { value: "12345" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "פתיחת כרטיס" }));

    expect(createTicket).not.toHaveBeenCalled();
    expect(within(dialog).getByText("צריך שם לקוחה.")).toBeInTheDocument();
    expect(within(dialog).getByText("מספר הטלפון אינו תקין.")).toBeInTheDocument();
    expect(within(dialog).getByText("צריך תאריך יעד.")).toBeInTheDocument();
  });

  it("WARNS on a past due date and never blocks it", async () => {
    // The server agrees: no lower bound, 200 on create and on update. A dress
    // that was due yesterday is exactly the ticket a boutique most needs to
    // open, and a form that refuses it sends the seamstress to WhatsApp.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    createTicket.mockResolvedValue(ticket({ id: T2, customer_name: "רותם כהן" }));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");
    fireEvent.change(within(dialog).getByLabelText("שם הלקוחה"), {
      target: { value: "רותם כהן" },
    });
    fireEvent.change(within(dialog).getByLabelText("טלפון"), {
      target: { value: "052-1234567" },
    });
    fireEvent.change(within(dialog).getByLabelText("תאריך יעד"), {
      target: { value: "2026-07-01" },
    });

    expect(within(dialog).getByText("התאריך שנבחר כבר עבר. אפשר להמשיך.")).toBeInTheDocument();
    // No `min` attribute either — the warning is the whole mechanism.
    expect(within(dialog).getByLabelText("תאריך יעד")).not.toHaveAttribute("min");

    fireEvent.click(within(dialog).getByRole("button", { name: "פתיחת כרטיס" }));
    await waitFor(() => expect(createTicket).toHaveBeenCalledTimes(1));
    expect(createTicket).toHaveBeenCalledWith({
      customer_name: "רותם כהן",
      customer_phone: "052-1234567",
      due_date: "2026-07-01",
      effort_band: "one_hour",
      assigned_staff_user_id: null,
      dress_id: null,
      dress_name: null,
      dress_size: null,
      notes: null,
    });
  });

  it("closes on success and announces the BRIDE, because focus went back to the trigger", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    createTicket.mockResolvedValue(ticket({ id: T2, customer_name: "רותם כהן" }));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");
    fireEvent.change(within(dialog).getByLabelText("שם הלקוחה"), {
      target: { value: "רותם כהן" },
    });
    fireEvent.change(within(dialog).getByLabelText("טלפון"), {
      target: { value: "0521234567" },
    });
    fireEvent.change(within(dialog).getByLabelText("תאריך יעד"), {
      target: { value: "2026-09-01" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "פתיחת כרטיס" }));

    await waitFor(() => expect((dialog as HTMLDialogElement).open).toBe(false));
    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("רותם כהן — נפתח כרטיס.");
    // …and the card is on the board, patched from the response rather than
    // waited for.
    expect(
      within(screen.getByRole("list", { name: "התקבל" })).getByText("רותם כהן"),
    ).toBeInTheDocument();
  });

  it("counts the notes field so «the board never truncates a note» is honest", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");
    const notes = within(dialog).getByLabelText("הערות");

    expect(notes).toHaveAttribute("maxlength", "500");
    fireEvent.change(notes, { target: { value: "להרים" } });
    expect(within(dialog).getByText(/5 \/ 500/)).toBeInTheDocument();
  });

  it("opens «עריכה» prefilled, with the customer as a STATIC LINE and not a field", async () => {
    // A ticket opened for the wrong bride is a delete, not an edit.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "עריכה — מיכל לוי" }));
    const dialog = openDialog("עריכת כרטיס");

    expect(within(dialog).queryByLabelText("שם הלקוחה")).toBeNull();
    expect(within(dialog).queryByLabelText("טלפון")).toBeNull();
    expect(within(dialog).getByText("מיכל לוי")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("תאריך יעד")).toHaveValue("2026-08-12");
    expect(within(dialog).getByLabelText("הערכת זמן")).toHaveValue("two_hours");
    expect(within(dialog).getByLabelText("שם השמלה")).toHaveValue("ולנטינה");
  });

  it("round-trips a due date and a band through a FULL REPLACE and renders the server's row", async () => {
    // Every editable field, never a partial patch: with optional fields an
    // omitted key and an explicitly cleared one are the same request, so a
    // console that forgot `notes` would silently delete a bride's measurements.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    updateTicket.mockResolvedValue(
      ticket({ due_date: "2026-09-30", effort_minutes: 240 }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "עריכה — מיכל לוי" }));
    const dialog = openDialog("עריכת כרטיס");
    fireEvent.change(within(dialog).getByLabelText("תאריך יעד"), {
      target: { value: "2026-09-30" },
    });
    fireEvent.change(within(dialog).getByLabelText("הערכת זמן"), {
      target: { value: "half_day" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "שמירה" }));

    await waitFor(() => expect(updateTicket).toHaveBeenCalledTimes(1));
    expect(updateTicket).toHaveBeenCalledWith(T1, {
      due_date: "2026-09-30",
      effort_band: "half_day",
      dress_id: null,
      dress_name: "ולנטינה",
      dress_size: "38",
      notes: "להרים 4 ס״מ, לצרף חגורה",
    });
    await waitFor(() => expect(screen.getByText(/30\.9\.2026/)).toBeInTheDocument());
    expect(screen.getByText(/חצי יום/)).toBeInTheDocument();
  });

  it("puts a server refusal in ONE alert INSIDE the dialog, above the footer", async () => {
    // ⚠ Never a Toast behind a modal, and never a message the dialog dismisses
    // itself to show. This is where the horizon 400 lands, and it is what keeps
    // main.py's ENGLISH body out of a Hebrew dialog.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    updateTicket.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "due_date is too far in the future"),
    );
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "עריכה — מיכל לוי" }));
    const dialog = openDialog("עריכת כרטיס");
    fireEvent.click(within(dialog).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(within(dialog).getByRole("alert")).toHaveTextContent(
        "הפעולה נדחתה. כדאי לבדוק את הפרטים ולנסות שוב.",
      ),
    );
    expect((dialog as HTMLDialogElement).open).toBe(true);
    expect(dialog.textContent).not.toContain("due_date is too far");
  });
});

// --- C6: both dialogs mount at SECTION level ---------------------------------

describe("C6 — the dialogs are siblings of the column grid", () => {
  it("survives three ticks that reorder and REMOVE cards, with the draft intact", async () => {
    // Their open state and draft live in the section's state keyed by ticket id,
    // so a repaint of the list they were opened from cannot unmount them.
    getAtelierBoard.mockResolvedValue(board([ticket(), ticket({ id: T2, customer_name: "רותם" })]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "עריכה — מיכל לוי" }));
    const dialog = openDialog("עריכת כרטיס");
    fireEvent.change(within(dialog).getByLabelText("הערות"), {
      target: { value: "לקצר עוד 2 ס״מ" },
    });

    // A colleague deletes it, then the board comes back reordered.
    getAtelierBoard.mockResolvedValue(board([ticket({ id: T2, customer_name: "רותם" })]));
    await advanceTimers(POLL_INTERVAL_MS);
    await advanceTimers(POLL_INTERVAL_MS);
    await advanceTimers(POLL_INTERVAL_MS);

    expect((dialog as HTMLDialogElement).open).toBe(true);
    expect(within(dialog).getByLabelText("הערות")).toHaveValue("לקצר עוד 2 ס״מ");
  });
});

// --- §7.4: «מחיקה» asks before it writes -------------------------------------

describe("the delete confirm", () => {
  it("calls NOTHING until the confirm is activated, and names the bride", async () => {
    // There is no un-delete, which is why this is the one act on the board that
    // asks before it writes.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    deleteTicket.mockResolvedValue({ ok: true });
    const { container } = mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "מחיקה — מיכל לוי" }));
    const dialog = openDialog("מחיקת כרטיס");

    expect(deleteTicket).not.toHaveBeenCalled();
    expect(dialog).toHaveTextContent("הכרטיס של מיכל לוי יימחק מהלוח. לא ניתן לשחזר אותו.");
    // The bride's name rides a bare <bdi> here too.
    expect(within(dialog).getByText("מיכל לוי").tagName).toBe("BDI");

    fireEvent.click(within(dialog).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(deleteTicket).toHaveBeenCalledWith(T1));
    // The card leaves the board — asserted on the card itself, because the CUE
    // names the bride too and is the only thing left that says which ticket
    // went.
    await waitFor(() => expect(container.querySelectorAll("[data-ticket-id]")).toHaveLength(0));
    expect(screen.getByTestId("atelier-cue")).toHaveTextContent("מיכל לוי — הכרטיס נמחק.");
  });

  it("dismisses without writing", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "מחיקה — מיכל לוי" }));
    const dialog = openDialog("מחיקת כרטיס");
    fireEvent.click(within(dialog).getByRole("button", { name: "ביטול" }));

    await waitFor(() => expect((dialog as HTMLDialogElement).open).toBe(false));
    expect(deleteTicket).not.toHaveBeenCalled();
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
  });
});

// --- C7: the terminal DEFERS while a dialog is open --------------------------

describe("C7 — a terminal while a dialog is open", () => {
  it("keeps the dialog and its typed draft, and renders the terminal only after dismissal", async () => {
    // A terminal transition that unmounted the section under an open dialog
    // would silently discard typed work.
    getAtelierBoard.mockResolvedValueOnce(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    const dialog = openDialog("כרטיס חדש");
    fireEvent.change(within(dialog).getByLabelText("שם הלקוחה"), {
      target: { value: "רותם כהן" },
    });

    const before = getAtelierBoard.mock.calls.length;
    getAtelierBoard.mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "gone"));
    await advanceTimers(POLL_INTERVAL_MS);
    // The 401 actually LANDED — without this the rest of the test asserts that
    // nothing happened after nothing happened.
    expect(getAtelierBoard.mock.calls.length).toBeGreaterThan(before);

    // ⚠ RE-QUERIED FROM THE LIVE DOCUMENT, never the node captured before the
    // tick. A detached <dialog> keeps its `open` attribute and all its children,
    // so asserting on the captured reference passes just as well when the
    // section unmounted underneath it — the same class of vacuity as a focus
    // test that never reproduces the blur.
    const live = screen.getByRole("dialog", { hidden: true, name: "כרטיס חדש" });
    expect(live).toBeInTheDocument();
    expect((live as HTMLDialogElement).open).toBe(true);
    expect(within(live).getByLabelText("שם הלקוחה")).toHaveValue("רותם כהן");
    expect(screen.queryByText("תוקף החיבור פג. צריך להתחבר מחדש.")).toBeNull();

    fireEvent.click(within(live).getByRole("button", { name: "ביטול" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("תוקף החיבור פג."),
    );
    // …and it takes focus: the dialog's own focus-return targets a trigger the
    // terminal panel has just unmounted, which would otherwise land on <body>.
    expect(document.activeElement).toBe(screen.getByRole("alert"));
  });
});

// --- §3.3 / C4: THE FIVE FOCUS DESTINATIONS ---------------------------------
//
// ⚠ A SUCCESSFUL ADVANCE MOVES THE CARD TO A DIFFERENT COLUMN, so the tapped
// control unmounts and the browser drops document.activeElement to <body>. On
// this surface that is not a side effect — IT IS WHAT THE FEATURE DOES. This bug
// class has shipped THREE times in this repo and axe walked past it every time,
// because axe cannot see a focus move that never happened.
//
// Each test below asserts `document.activeElement` IS the expected node, never
// merely that the node exists: a shipped success-path focus test was once
// vacuous precisely because jsdom does not blur a disabled element.

describe("the five focus destinations a repaint or a mutation can strand", () => {
  it("1 — a successful advance lands on the SAME ticket's control in its NEW column", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockResolvedValue(
      ticket({ stage: "in_progress", in_progress_at: "2026-08-04T11:00:00Z" }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" });
    control.focus();
    await clickAndSettle(control);

    const moved = within(screen.getByRole("list", { name: "בעבודה" })).getByRole("button", {
      name: "לשלב הבא — מיכל לוי",
    });
    // …and it is a DIFFERENT node from the one she tapped, which is what makes
    // this a move rather than a rename.
    expect(moved).not.toBe(control);
    expect(control.isConnected).toBe(false);
    expect(document.activeElement).toBe(moved);
  });

  it("1b — an advance onto `delivered` lands on ANY control of that ticket, not <body>", async () => {
    // The destination card has no «לשלב הבא» at all, so the id-keyed lookup
    // falls through to the next control on the same ticket.
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "ready" })]));
    advanceStage.mockResolvedValue(
      ticket({ stage: "delivered", delivered_at: "2026-08-04T11:00:00Z" }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" });
    control.focus();
    await clickAndSettle(control);

    expect(
      within(screen.getByRole("list", { name: "נמסר" })).getByText("מיכל לוי"),
    ).toBeInTheDocument();
    expect(document.activeElement).not.toBe(document.body);
    expect(
      (document.activeElement as HTMLElement).closest("[data-ticket-id]"),
    ).toHaveAttribute("data-ticket-id", T1);
  });

  it("2 — ANY refused mutation lands on the in-card alert", async () => {
    // ⚠ THE FAILURE PATH IS THE ONE THAT GETS FORGOTTEN: one shipped surface
    // compensated on its success path and restored nothing in its catch, and
    // that was a Level A defect found in review and not in CI.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockRejectedValue(new ApiError(409, "TICKET_STAGE_CONFLICT", "moved"));
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" });
    control.focus();
    await clickAndSettle(control);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("הכרטיס כבר התקדם.");
    expect(document.activeElement).toBe(alert);
  });

  it("3 — a successful poll that clears the focused alert hands focus back to that card's control", async () => {
    // ⚠ EASY TO MISS because the alert is cleared about five seconds later WITH
    // NO USER ACTION AT ALL, and the departing-card rescue cannot cover it: the
    // card is still in the list.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    advanceStage.mockRejectedValue(new ApiError(409, "TICKET_STAGE_CONFLICT", "moved"));
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" });
    control.focus();
    await clickAndSettle(control);
    expect(document.activeElement).toBe(screen.getByRole("alert"));

    await advanceTimers(POLL_INTERVAL_MS);
    expect(screen.queryByRole("alert")).toBeNull();

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toHaveAccessibleName("לשלב הבא — מיכל לוי");
  });

  it("4 — a successful DELETE lands on the departing card's own column heading", async () => {
    // The card is gone entirely, so the id-keyed lookup has nothing to find.
    // Without the rescue, deleting the focused card drops focus to <body> on the
    // single most destructive act in the feature.
    getAtelierBoard.mockResolvedValue(
      board([ticket(), ticket({ id: T2, customer_name: "רותם כהן" })]),
    );
    deleteTicket.mockResolvedValue({ ok: true });
    const { container } = mount();
    await screen.findByText("רותם כהן");

    fireEvent.click(screen.getByRole("button", { name: "מחיקה — מיכל לוי" }));
    const dialog = openDialog("מחיקת כרטיס");
    // ⚠ `act`, and deliberately NOT `waitFor`. jsdom runs a native <dialog>'s
    // close-focus steps from a QUEUED TASK, where the platform runs them
    // synchronously inside close() — i.e. in the Modal child's effect, before
    // this section's. `waitFor` advances timers and therefore flushes that
    // deferred task, which restores focus toward a trigger that left with the
    // card and lands it on <body>: the assertion below would then be measuring
    // jsdom's queue rather than this component. `act` flushes React and the
    // promise chain and nothing else.
    await act(async () => {
      fireEvent.click(within(dialog).getByRole("button", { name: "מחיקה" }));
    });

    expect(container.querySelectorAll("[data-ticket-id]")).toHaveLength(1);
    expect(document.activeElement).toBe(
      screen.getAllByRole("heading", { level: 3 })[0],
    );
    expect(document.activeElement).toHaveTextContent("התקבל");
  });

  it("5a — a POLL that moves the focused card, because a COLLEAGUE advanced it", async () => {
    // ⚠ Five columns are five <ul>s, so a card changing stage UNMOUNTS from one
    // list and MOUNTS in another. Focus is lost with no user action at all, five
    // seconds after somebody else tapped a button on a different phone.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" });
    control.focus();

    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "qc" })]));
    await advanceTimers(POLL_INTERVAL_MS);

    const moved = await waitFor(() =>
      within(screen.getByRole("list", { name: "בקרה" })).getByRole("button", {
        name: "לשלב הבא — מיכל לוי",
      }),
    );
    expect(control.isConnected).toBe(false);
    expect(document.activeElement).toBe(moved);
  });

  it("5b — a POLL that DE-CONTROLS the focused card, because a COLLEAGUE claimed it", async () => {
    // ⚠ THE CASE A STAGE-KEYED CAPTURE WOULD MISS, and the reason the capture is
    // UNCONDITIONAL: the stage did not change, no alert is involved and the
    // ticket is still in the payload — so every predicate the deck proposed is
    // false, and the card she is standing on simply loses every control she had.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    mount({ role: "seamstress", selfId: NOA_ID });
    await screen.findByText("מיכל לוי");

    const claim = screen.getByRole("button", { name: "לקחת — מיכל לוי" });
    claim.focus();

    getAtelierBoard.mockResolvedValue(
      board([ticket({ assigned_staff_user_id: OTHER_SEAMSTRESS })], {
        seamstresses: [
          { id: NOA_ID, display_name: "נועה לוי", assignable: true },
          { id: OTHER_SEAMSTRESS, display_name: "רותם", assignable: true },
        ],
      }),
    );
    await advanceTimers(POLL_INTERVAL_MS);

    await waitFor(() => expect(screen.queryByRole("button", { name: /לקחת/ })).toBeNull());
    // The card stayed put, so the destination is its own column's heading.
    expect(document.activeElement).toBe(screen.getAllByRole("heading", { level: 3 })[0]);
    expect(document.activeElement).toHaveTextContent("התקבל");
  });

  it("steals NOTHING back that the user moved while a write was in flight", async () => {
    // ⚠ THE `document.activeElement === document.body` GUARD IS WHAT MAKES THE
    // UNCONDITIONAL CAPTURE FREE — and this is the fixture that exercises it: she
    // taps «לשלב הבא», then tabs away while the request is in the air. The
    // capture is already recorded, so without the guard the response would drag
    // her back into a card she deliberately left.
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    let settle: (value: AtelierTicket) => void = () => {};
    advanceStage.mockReturnValue(
      new Promise<AtelierTicket>((resolve) => {
        settle = resolve;
      }),
    );
    mount();
    await screen.findByText("מיכל לוי");

    const control = screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" });
    control.focus();
    fireEvent.click(control);

    const pauseControl = screen.getByRole("button", { name: "השהיה — לוח התפירה" });
    pauseControl.focus();

    await act(async () => {
      settle(ticket({ stage: "in_progress", in_progress_at: "2026-08-04T11:00:00Z" }));
    });
    expect(
      within(screen.getByRole("list", { name: "בעבודה" })).getByText("מיכל לוי"),
    ).toBeInTheDocument();

    expect(document.activeElement).toBe(pauseControl);
  });
});

// --- §3.4 / C12: operable with no pointer, and no drag affordance anywhere ---

describe("the keyboard sweep", () => {
  it("makes every act a real focusable control, never a div with a role", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    mount();
    await screen.findByText("מיכל לוי");

    for (const name of [
      "לשלב הבא — מיכל לוי",
      "העברה — מיכל לוי",
      "שיוך — מיכל לוי",
      "ביטול שלב — מיכל לוי",
      "עריכה — מיכל לוי",
      "מחיקה — מיכל לוי",
    ]) {
      const control = screen.getByRole("button", { name });
      expect(control.tagName).toBe("BUTTON");
      expect(control).not.toHaveAttribute("tabindex", "-1");
    }
    for (const name of ["העברה לשלב — מיכל לוי", "תופרת — מיכל לוי"]) {
      expect(screen.getByRole("combobox", { name }).tagName).toBe("SELECT");
    }
    for (const chip of within(
      screen.getByRole("navigation", { name: "מעבר לשלב" }),
    ).getAllByRole("link")) {
      expect(chip.tagName).toBe("A");
    }
  });

  it("has NO drag handler and NO draggable attribute anywhere in the tree", async () => {
    // ⚠ A kanban is a drag-shaped idea and this one ships with NO drag
    // affordance at all. Every accessible DnD is a keyboard alternative bolted
    // onto a gesture, so the button path gets built either way, and WCAG 2.5.7
    // requires the single-pointer alternative regardless. THE ALTERNATIVE IS THE
    // INTERFACE.
    //
    // Read as SOURCE as well as as DOM: a handler wired to a child component
    // would never reach the rendered attributes.
    // `process.cwd()` is apps/manage under vitest; `import.meta.url` is not a
    // file: URL there.
    const source = readFileSync(
      resolve(process.cwd(), "src/components/AtelierSection.tsx"),
      "utf-8",
    );
    for (const banned of [
      "onDragStart",
      "onDragOver",
      "onDragEnd",
      "onDrop",
      "draggable",
      "dnd",
      "aria-grabbed",
    ]) {
      expect(source).not.toContain(banned);
    }

    getAtelierBoard.mockResolvedValue(board([ticket({ stage: "in_progress" })]));
    const { container } = mount();
    await screen.findByText("מיכל לוי");

    expect(container.querySelectorAll("[draggable]")).toHaveLength(0);
    expect(container.querySelectorAll("[aria-grabbed]")).toHaveLength(0);
    expect(container.querySelectorAll('[role="application"]')).toHaveLength(0);
    expect(container.querySelectorAll('[role="grid"]')).toHaveLength(0);
  });
});

// --- axe: necessary, and EXPLICITLY not sufficient ---------------------------

describe("axe", () => {
  it("finds zero violations on the loaded board", async () => {
    // ⚠ EXPLICITLY NOT SUFFICIENT. axe has NO rule for SC 2.2.2 and cannot see a
    // focus move that never happened, so the five focus tests above and the
    // pause assertions are the only automated coverage of a LEGAL requirement.
    // Neither set may be dropped as redundant with this row, now or in any later
    // tidy-up.
    getAtelierBoard.mockResolvedValue(
      board([
        ticket({ stage: "in_progress", overdue: true }),
        ticket({ id: T2, customer_name: "רותם כהן", assigned_staff_user_id: NOA_ID }),
      ]),
    );
    const { container } = renderInShell(<AtelierSection selfId={OWNER_ID} role="owner" />);
    await screen.findByText("מיכל לוי");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });

  it("finds zero violations on the EMPTY board a new boutique sees first", async () => {
    getAtelierBoard.mockResolvedValue(board([]));
    const { container } = renderInShell(<AtelierSection selfId={OWNER_ID} role="owner" />);
    await screen.findByText("אין עדיין כרטיסי תפירה");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });

  it("finds zero violations with the intake dialog open", async () => {
    getAtelierBoard.mockResolvedValue(board([ticket()]));
    const { container } = renderInShell(<AtelierSection selfId={OWNER_ID} role="owner" />);
    await screen.findByText("מיכל לוי");

    fireEvent.click(screen.getByRole("button", { name: "כרטיס חדש" }));
    openDialog("כרטיס חדש");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
