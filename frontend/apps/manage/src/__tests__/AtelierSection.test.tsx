import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3) and 07:07 in New York — and the test
// script pins TZ=America/New_York, so an unzoned read prints 07:07 and every
// time assertion below fails loudly rather than quietly.
const NOW = "2026-08-04T11:07:00Z";

const OWNER_ID = "11111111-1111-1111-1111-111111111111";
const NOA_ID = "22222222-2222-2222-2222-222222222222";
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

function mount(props: { selfId?: string; role?: string } = {}) {
  return render(<AtelierSection selfId={props.selfId ?? OWNER_ID} role={props.role ?? "owner"} />);
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getAtelierBoard.mockReset();
  advanceStage.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

async function advanceTimers(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
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

    fireEvent.click(screen.getByRole("button", { name: "לשלב הבא — מיכל לוי" }));

    await waitFor(() =>
      expect(
        within(screen.getByRole("list", { name: "בעבודה" })).getByText("מיכל לוי"),
      ).toBeInTheDocument(),
    );
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
