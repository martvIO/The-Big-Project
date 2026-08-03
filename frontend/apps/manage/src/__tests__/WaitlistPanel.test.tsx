import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { DispatchResult, Room, Waitlist, WaitlistEntry } from "../api";
import { WaitlistPanel } from "../components/WaitlistPanel";

// ⚠ WaitlistPanel is rendered DIRECTLY here, and that is the one place this
// suite diverges from RoomsPanel.test.tsx — which mounts through FloorPanel
// because a tile's correctness depends on the real poll above it. This panel
// owns no timer, no pause control and no announced region, so everything below
// (the four verbs, the three reveals, the six focus moves, every refusal
// sentence) is reachable with a harness that holds the state FloorPanel holds
// and a `mutate` that keeps FloorPanel's contract: null on success or on a
// terminal 401/403, the error otherwise.
//
// The harness is not a stub of the mechanisms under test. It is a stub of the
// POLL, which this panel deliberately does not have.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      callQueueTicket: vi.fn(),
      assignFromQueue: vi.fn(),
      skipQueueTicket: vi.fn(),
      removeQueueTicket: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const callQueueTicket = vi.mocked(api.callQueueTicket);
const assignFromQueue = vi.mocked(api.assignFromQueue);
const skipQueueTicket = vi.mocked(api.skipQueueTicket);
const removeQueueTicket = vi.mocked(api.removeQueueTicket);

// The test script pins TZ=America/New_York, so an unzoned read prints a
// different hour and any time assertion below would fail loudly. Nothing here
// formats a clock: the wait line is arithmetic on two ISO instants and involves
// no timezone at all.
const NOW = "2026-08-04T11:07:00Z";
const ARRIVED_23 = "2026-08-04T10:44:00Z"; // 23 minutes before NOW
const ARRIVED_JUST = "2026-08-04T11:06:30Z"; // 30 seconds before NOW

const ENTRY_A = "aaaaaaaa-0000-0000-0000-00000000000a";
const ENTRY_B = "bbbbbbbb-0000-0000-0000-00000000000b";
const ROOM_A = "cccccccc-0000-0000-0000-00000000000c";
const ROOM_B = "dddddddd-0000-0000-0000-00000000000d";
const STAFF_ID = "eeeeeeee-0000-0000-0000-00000000000e";

function entry(overrides: Partial<WaitlistEntry> = {}): WaitlistEntry {
  return {
    id: ENTRY_A,
    name: "מיכל אברהם",
    visit_type: "bride",
    position: 1,
    arrived_at: ARRIVED_23,
    called: false,
    skip_count: 0,
    duplicate: false,
    ...overrides,
  };
}

function room(overrides: Partial<Room> = {}): Room {
  return {
    id: ROOM_A,
    label: "חדר 1",
    sort_order: 0,
    is_active: true,
    assignment: null,
    ...overrides,
  };
}

function occupied(overrides: Partial<Room> = {}): Room {
  return room({
    assignment: {
      id: "ffffffff-0000-0000-0000-00000000000f",
      staff_user_id: STAFF_ID,
      staff_display_name: "דנה כהן",
      staff_role: "seamstress",
      client_label: null,
      booking_id: null,
      assigned_at: NOW,
      dresses: [],
    },
    ...overrides,
  });
}

function list(entries: WaitlistEntry[], truncated = false): Waitlist {
  return { entries, truncated };
}

// The harness holds exactly what FloorPanel holds and nothing else: the two
// lists, the success counter, and `mutate`'s null-or-error contract.
function Harness(props: {
  initial: Waitlist | null;
  rooms?: Room[] | null;
  role?: string;
  paused?: boolean;
  serverNow?: string | null;
  onCue: (cue: { text: string; name: string | null }) => void;
  register?: (api: {
    tick: (next?: Waitlist, rooms?: Room[]) => void;
  }) => void;
}) {
  const [waitlist, setWaitlist] = useState<Waitlist | null>(props.initial);
  const [rooms, setRooms] = useState<Room[] | null>(props.rooms ?? [room()]);
  const [fetchCount, setFetchCount] = useState(0);

  props.register?.({
    tick: (next, nextRooms) => {
      if (next !== undefined) {
        setWaitlist(next);
      }
      if (nextRooms !== undefined) {
        setRooms(nextRooms);
      }
      setFetchCount((current) => current + 1);
    },
  });

  return (
    <WaitlistPanel
      waitlist={waitlist}
      rooms={rooms}
      serverNow={props.serverNow === undefined ? NOW : props.serverNow}
      fetchCount={fetchCount}
      role={props.role ?? "owner"}
      paused={props.paused ?? false}
      mutate={async (fn) => {
        try {
          await fn();
          return null;
        } catch (error) {
          return error;
        }
      }}
      onWaitlist={(update) => setWaitlist((current) => update(current ?? list([])))}
      onRooms={(update) => setRooms((current) => update(current ?? []))}
      onCue={props.onCue}
    />
  );
}

interface Mounted {
  cue: ReturnType<typeof vi.fn>;
  tick: (next?: Waitlist, rooms?: Room[]) => void;
}

function mount(props: Omit<Parameters<typeof Harness>[0], "onCue" | "register"> ): Mounted {
  const cue = vi.fn();
  let control: { tick: (next?: Waitlist, rooms?: Room[]) => void } | null = null;
  render(<Harness {...props} onCue={cue} register={(handle) => (control = handle)} />);
  return {
    cue,
    tick: (next, rooms) => {
      act(() => {
        (control as unknown as { tick: (n?: Waitlist, r?: Room[]) => void }).tick(next, rooms);
      });
    },
  };
}

// Rows carry their entry id as a data attribute — the same shape the tiles and
// the staff cards use, and what the focus rescue reads.
function row(id: string): HTMLElement {
  const node = document.querySelector(`[data-entry-id="${id}"]`);
  if (node === null) {
    throw new Error(`no row for entry ${id}`);
  }
  return node as HTMLElement;
}

// A promise a test resolves itself, so the request can be observed IN FLIGHT.
function deferred<T>() {
  let settle: (value: T) => void = () => {};
  let fail: (reason: unknown) => void = () => {};
  const promise = new Promise<T>((resolve, reject) => {
    settle = resolve;
    fail = reject;
  });
  return { promise, settle, fail };
}

beforeEach(() => {
  callQueueTicket.mockReset();
  assignFromQueue.mockReset();
  skipQueueTicket.mockReset();
  removeQueueTicket.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// --- W-load, W-empty, W-list, W-truncated, W-noroom -------------------------

describe("every state the panel has, not just the populated one", () => {
  it("renders NOTHING at all on the first tick", () => {
    // W-load. FloorPanel's own Skeleton covers the screen; a second skeleton
    // over a fetch nothing has seen produce anything is a second thing claiming
    // to be current.
    mount({ initial: null });
    expect(screen.queryByRole("heading", { level: 3 })).not.toBeInTheDocument();
  });

  it("renders the heading in EVERY populated state, including the empty one", () => {
    // The h3 is MOVES 3, 4 and 6's focus-rescue target, so it may not be
    // conditional on there being rows.
    mount({ initial: list([]) });
    const heading = screen.getByRole("heading", { level: 3, name: "ממתינות בתור" });
    expect(heading).toHaveAttribute("tabindex", "-1");
    expect(screen.getByText("אין ממתינות בתור")).toBeInTheDocument();
  });

  it("offers NO body and NO action in the empty state, for any role", () => {
    // The opposite of rooms.empty, where the CTA is the whole point. There is
    // nothing to configure — the queue fills when a woman scans the printed QR
    // at the door — so a body would explain a process the staffer is not part
    // of and an action slot would offer a door that leads nowhere.
    mount({ initial: list([]) });
    expect(screen.queryAllByRole("button")).toEqual([]);
  });

  it("renders position, name, visit type and wait time, with the right bidi on each", () => {
    mount({ initial: list([entry()]) });
    const li = row(ENTRY_A);

    // A numeric run inside an RTL sentence.
    const position = within(li).getByText("1");
    expect(position.tagName).toBe("BDI");
    expect(position).toHaveAttribute("dir", "ltr");
    expect(position.className).toContain("tabular-nums");

    // ⚠ A BARE <bdi>. dir="ltr" on «מיכל אברהם» reverses its words, and it is
    // the bidi defect that LOOKS DELIBERATE.
    const name = within(li).getByText("מיכל אברהם");
    expect(name.tagName).toBe("BDI");
    expect(name).not.toHaveAttribute("dir");
    expect(name.className).not.toContain("truncate");
    expect(name.className).not.toContain("ellipsis");

    expect(within(li).getByText(/מדידת כלה/)).toBeInTheDocument();
    expect(within(li).getByText(/ממתינה/)).toHaveTextContent("ממתינה 23 דק'");
  });

  it("spells the bride arm the way the form she filled in spells it", () => {
    // Two apps, two bundles, one fact. A manager reading «שמלת כלה» beside a
    // customer who ticked «מדידת כלה» has no way to know they are the same.
    mount({ initial: list([entry(), entry({ id: ENTRY_B, visit_type: "evening" })]) });
    expect(within(row(ENTRY_A)).getByText(/מדידת כלה/)).toBeInTheDocument();
    expect(within(row(ENTRY_B)).getByText(/שמלת ערב/)).toBeInTheDocument();
  });

  it("renders «הגיעה זה עתה» for the first minute and for the clamped negative", () => {
    // `arrived_at` is created_at, whose DEFAULT now() is the DATABASE host's
    // clock, while server_now comes from the service's Python one — so
    // arrived_at > serverNow is representable and a raw subtraction can go
    // negative. «ממתינה 0 דק'» is also bad Hebrew and is what EVERY arrival
    // would read for its first minute.
    mount({
      initial: list([
        entry({ arrived_at: ARRIVED_JUST }),
        entry({ id: ENTRY_B, arrived_at: "2026-08-04T11:09:00Z" }),
      ]),
    });
    expect(within(row(ENTRY_A)).getByText(/הגיעה זה עתה/)).toBeInTheDocument();
    expect(within(row(ENTRY_B)).getByText(/הגיעה זה עתה/)).toBeInTheDocument();
  });

  it("uses the QUEUE's wait wording and never the ROOM's elapsed line", () => {
    // ⚠ elapsedLine hard-codes rooms.elapsedJustNow and rooms.elapsed, so
    // calling it here would render «כבר 23 דק'» — *already 23 min*, the room's
    // sentence — about a woman who has not been in a room, and would leave this
    // feature's two keys DEAD, GREEN AND UNUSED, because i18n.test.ts counts
    // entries and never checks that a key is reached. This assertion is the only
    // thing in the repo that can catch it.
    mount({ initial: list([entry(), entry({ id: ENTRY_B, arrived_at: ARRIVED_JUST })]) });
    expect(screen.queryByText(/כבר/)).not.toBeInTheDocument();
    expect(within(row(ENTRY_A)).getByText(/ממתינה/)).toHaveTextContent("ממתינה 23 דק'");
    expect(within(row(ENTRY_B)).getByText(/הגיעה זה עתה/)).toBeInTheDocument();
  });

  it("carries AT MOST ONE Badge per row, and it is «נקראה»", () => {
    // A second pill in 295px teaches the reader to scan colours instead of
    // words. The duplicate flag and the skip count are LINES.
    mount({
      initial: list([
        entry({ called: true, duplicate: true, skip_count: 1 }),
        entry({ id: ENTRY_B, position: 2 }),
      ]),
    });
    const called = row(ENTRY_A);
    expect(within(called).getAllByText("נקראה")).toHaveLength(1);
    expect(within(called).getByText("יש עוד כניסה פעילה היום עם אותו מספר טלפון.")).toBeInTheDocument();
    expect(within(called).getByText("דילגו עליה פעם אחת")).toBeInTheDocument();
    expect(within(row(ENTRY_B)).queryByText("נקראה")).not.toBeInTheDocument();
  });

  it("flags BOTH rows of a duplicate pair and neither hides, dims nor reorders either", () => {
    // A panel that auto-selected one would be deciding, on a name match, which
    // of two women loses her place. The position numbers already say which
    // arrived first.
    mount({
      initial: list([
        entry({ name: "נועה בר", duplicate: true }),
        entry({ id: ENTRY_B, name: "נועה בר", position: 2, duplicate: true }),
      ]),
    });
    for (const id of [ENTRY_A, ENTRY_B]) {
      const li = row(id);
      expect(within(li).getByText("יש עוד כניסה פעילה היום עם אותו מספר טלפון.")).toBeInTheDocument();
      expect(li.className).not.toContain("opacity-");
      expect(within(li).getByRole("button", { name: "הסרה — נועה בר" })).toBeInTheDocument();
    }
    const ids = Array.from(document.querySelectorAll("[data-entry-id]")).map((node) =>
      node.getAttribute("data-entry-id"),
    );
    expect(ids).toEqual([ENTRY_A, ENTRY_B]);
  });

  it("renders the truncation line with no count and no limit", () => {
    mount({ initial: list([entry()], true) });
    const line = screen.getByText(
      "הרשימה חלקית. הממתינות שהגיעו מאוחר יותר אינן מופיעות כאן.",
    );
    expect(line.textContent).not.toMatch(/\d/);
  });

  it("renders the no-free-room line ONCE, at panel level, and drops every assign control", () => {
    // ⚠ CORRECTS spec D17's "the row carries one line saying so": with forty
    // rows that is forty identical sentences, and the fact is about the rooms
    // rather than about any entry. Never a disabled button — a control that
    // refuses is a 403's cousin on a screen where 403 is terminal.
    mount({
      initial: list([entry(), entry({ id: ENTRY_B, position: 2 })]),
      rooms: [occupied(), room({ id: ROOM_B, label: "חדר 2", is_active: false })],
    });
    expect(screen.getAllByText("אין חדר פנוי כרגע.")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /שבצי לחדר/ })).not.toBeInTheDocument();
    // Not merely absent-and-disabled: absent.
    for (const button of screen.getAllByRole("button")) {
      expect(button).not.toBeDisabled();
    }
  });

  it("renders NO href and NO `to` carrying an entry id anywhere", () => {
    // A29. The row carries F33's position-page CAPABILITY — whoever holds the
    // ticket id can read that ticket's page — and the console must never render
    // it as a link. A DOM query and not a grep: a grep passes when the link is
    // built by string concatenation.
    mount({
      initial: list([entry({ called: true, duplicate: true, skip_count: 1 }), entry({ id: ENTRY_B, position: 2 })]),
    });
    for (const node of Array.from(document.querySelectorAll("*"))) {
      for (const attribute of Array.from(node.attributes)) {
        if (attribute.name === "data-entry-id") {
          continue;
        }
        expect(attribute.value).not.toContain(ENTRY_A);
        expect(attribute.value).not.toContain(ENTRY_B);
      }
    }
    expect(document.querySelectorAll("a")).toHaveLength(0);
  });
});

// --- which control EXISTS is the authorization axis, rendered ---------------

describe("the four controls and who has them", () => {
  it("gives all five roles «קראי» and «שבצי לחדר»", () => {
    for (const role of ["owner", "shift_manager", "reception", "sales_assistant", "seamstress"]) {
      const view = render(
        <Harness initial={list([entry()])} role={role} onCue={vi.fn()} />,
      );
      expect(screen.getByRole("button", { name: "קראי — מיכל אברהם" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" })).toBeInTheDocument();
      view.unmount();
    }
  });

  it("ABSENTS «דלגי» and «הסרה» for the three floor roles — no disabled control, no explanation", () => {
    // ⚠ A 403 is TERMINAL for the whole floor screen, and for these three roles
    // that is the entire product going dark — so a control the server will
    // refuse is never rendered at all. No disabled button, no lock glyph, no
    // «אין לך הרשאה» line, no tooltip. The product cost is real and recorded:
    // a reception staffer cannot skip a no-show; she asks a shift manager.
    for (const role of ["reception", "sales_assistant", "seamstress"]) {
      const view = render(<Harness initial={list([entry()])} role={role} onCue={vi.fn()} />);
      expect(screen.queryByRole("button", { name: /^דלגי/ })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /^הסרה/ })).not.toBeInTheDocument();
      expect(screen.queryByText(/הרשאה/)).not.toBeInTheDocument();
      view.unmount();
    }
    render(<Harness initial={list([entry()])} role="shift_manager" onCue={vi.fn()} />);
    expect(screen.getByRole("button", { name: "דלגי — מיכל אברהם" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הסרה — מיכל אברהם" })).toBeInTheDocument();
  });

  it("puts every control at the 44px floor and none full-width on mobile", () => {
    // jsdom has no layout engine, so a MEASURED assertion would be vacuous —
    // the class is what carries the fact. sm is min-h-9 = 36px and under the
    // house floor, and four controls per row is where the temptation to reach
    // for it is highest in this codebase.
    mount({ initial: list([entry()]) });
    for (const button of within(row(ENTRY_A)).getAllByRole("button")) {
      expect(button.className).toContain("min-h-11");
      expect(button.className).not.toContain("w-full");
    }
  });

  it("gives «הסרה» the weight of the irreversible act and keeps the trigger out of red", () => {
    // DC-9 plus P-5. At 375 the wrapped four-button row distinguishes the one
    // irreversible control by WEIGHT rather than by reading order — but the
    // TRIGGER asks rather than removes, and a permanently red control on every
    // row of a list of waiting customers reads as a threat on a screen a
    // staffer opens fifty times a shift.
    mount({ initial: list([entry()]) });
    const li = row(ENTRY_A);
    const remove = within(li).getByRole("button", { name: "הסרה — מיכל אברהם" });
    expect(remove.className).toContain("border-ink");
    expect(remove.className).not.toContain("bg-danger");
    expect(within(li).getByRole("button", { name: "קראי — מיכל אברהם" }).className).toContain(
      "bg-transparent",
    );
    expect(within(li).getByRole("button", { name: "דלגי — מיכל אברהם" }).className).toContain(
      "bg-transparent",
    );
  });
});

// --- the verbs: every one patches from the SERVER's response ----------------

describe("the four verbs", () => {
  it("calls a customer, keeps «קראי», and writes the cue that names no send", () => {
    const called = list([entry({ called: true })]);
    callQueueTicket.mockResolvedValue(called);
    const view = mount({ initial: list([entry()]) });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    return waitFor(() => {
      expect(within(row(ENTRY_A)).getByText("נקראה")).toBeInTheDocument();
    }).then(() => {
      expect(callQueueTicket).toHaveBeenCalledWith(ENTRY_A);
      // ⚠ «נרשמה» and NEVER «נשלחה»: nothing is sent to anybody. `call` stamps a
      // timestamp, and that is what makes her page read «אפשר לגשת לדלפק».
      expect(view.cue).toHaveBeenCalledWith({ text: "הקריאה נרשמה.", name: null });
      // She did not come the first time; a re-call is what a manager does next.
      expect(screen.getByRole("button", { name: "קראי — מיכל אברהם" })).toBeInTheDocument();
    });
  });

  it("renders the FIRST timestamp's state on a second call, not this request's intent", async () => {
    // A second call is a 200 that writes nothing (`called_at IS NULL` keeps the
    // first timestamp), so the screen is IDENTICAL to the first success —
    // deliberately. Telling her she lost a race would be telling her she was
    // wrong when she was right. Patching optimistically is what would break it.
    const unchanged = list([entry({ called: true })]);
    callQueueTicket.mockResolvedValue(unchanged);
    const view = mount({ initial: unchanged });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    await waitFor(() => {
      expect(view.cue).toHaveBeenCalledWith({ text: "הקריאה נרשמה.", name: null });
    });
    expect(within(row(ENTRY_A)).getAllByText("נקראה")).toHaveLength(1);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("fires ONE request for a double tap", async () => {
    const gate = deferred<Waitlist>();
    callQueueTicket.mockReturnValue(gate.promise);
    mount({ initial: list([entry()]) });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    // The control is now `loading`, and @boutique/ui's Button is
    // disabled={disabled || loading} — so the second tap reaches nothing.
    expect(screen.getByRole("button", { name: "קראי — מיכל אברהם" })).toBeDisabled();
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    expect(callQueueTicket).toHaveBeenCalledTimes(1);
    await act(async () => {
      gate.settle(list([entry({ called: true })]));
    });
  });

  it("spins ONLY the tapped control and leaves every other row live", async () => {
    const gate = deferred<Waitlist>();
    callQueueTicket.mockReturnValue(gate.promise);
    mount({
      initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]),
    });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    expect(screen.getByRole("button", { name: "קראי — מיכל אברהם" })).toHaveAttribute("aria-busy");
    for (const name of ["דלגי — מיכל אברהם", "הסרה — מיכל אברהם", "קראי — נועה בר"]) {
      expect(screen.getByRole("button", { name })).not.toHaveAttribute("aria-busy");
      expect(screen.getByRole("button", { name })).not.toBeDisabled();
    }
    await act(async () => {
      gate.settle(list([entry({ called: true })]));
    });
  });

  it("push-assigns from the row's reveal and patches BOTH panels from one response", async () => {
    // A client that patched only the tile and waited up to five seconds for the
    // row to leave the list would render the same woman as in-service AND
    // waiting.
    const dispatched: DispatchResult = { room: occupied(), waitlist: list([]) };
    assignFromQueue.mockResolvedValue(dispatched);
    const view = mount({ initial: list([entry()]), rooms: [room(), room({ id: ROOM_B, label: "חדר 2" })] });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    const select = screen.getByLabelText("שיבוץ לחדר — מיכל אברהם");
    expect(select).toHaveValue(ROOM_A);
    act(() => {
      fireEvent.change(select, { target: { value: ROOM_B } });
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });

    await waitFor(() => {
      expect(screen.getByText("אין ממתינות בתור")).toBeInTheDocument();
    });
    expect(assignFromQueue).toHaveBeenCalledWith(ROOM_B, { queue_ticket_id: ENTRY_A });
    // Names the ROOM and never her.
    expect(view.cue).toHaveBeenCalledWith({ text: "הלקוחה שובצה: חדר 1.", name: "חדר 1" });
  });

  it("patches the TILE from the same response, not just the queue", async () => {
    // The other half of the one act, and it is observable from this panel: the
    // room the response says is now occupied stops being an assign option for
    // everyone still waiting. A client that patched only the queue would offer
    // that room to the next woman for up to five seconds.
    assignFromQueue.mockResolvedValue({
      room: occupied(),
      waitlist: list([entry({ id: ENTRY_B, name: "נועה בר", position: 1 })]),
    });
    mount({
      initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]),
      rooms: [room()],
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });
    await waitFor(() => {
      expect(screen.getByText("אין חדר פנוי כרגע.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /שבצי לחדר/ })).not.toBeInTheDocument();
  });

  it("offers the free active rooms only, with the first preselected and NO placeholder", () => {
    // No second fetch and no picker endpoint — the options are the rooms the
    // panel already holds. A <select> with zero real options is a dead control
    // that looks live, so an option-less picker is never rendered at all.
    mount({
      initial: list([entry()]),
      rooms: [
        occupied({ id: ROOM_A, label: "חדר 1" }),
        room({ id: ROOM_B, label: "חדר 2" }),
        room({ id: "99999999-0000-0000-0000-000000000099", label: "הבמה", is_active: false }),
      ],
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    const options = within(screen.getByLabelText("שיבוץ לחדר — מיכל אברהם")).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual(["חדר 2"]);
    expect(screen.getByLabelText("שיבוץ לחדר — מיכל אברהם")).toHaveValue(ROOM_B);
    expect(screen.getByLabelText("שיבוץ לחדר — מיכל אברהם").className).toContain("min-h-11");
  });

  it("skips on ONE tap at count zero, sending the count the row RENDERED", async () => {
    const moved = list([entry({ skip_count: 1, position: 2 })]);
    skipQueueTicket.mockResolvedValue(moved);
    const view = mount({ initial: list([entry()]) });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "דלגי — מיכל אברהם" }));
    });
    await waitFor(() => {
      expect(view.cue).toHaveBeenCalledWith({ text: "הועברה לסוף התור.", name: null });
    });
    expect(skipQueueTicket).toHaveBeenCalledWith(ENTRY_A, { seen_skip_count: 0 });
    expect(screen.queryByRole("button", { name: "אישור ההסרה" })).not.toBeInTheDocument();
  });

  it("opens a confirm on the SECOND skip, and its cue says she was REMOVED", async () => {
    // ⚠ Two cues for one control, chosen on what the CLIENT SENT — so it needs
    // nothing from a response that no longer carries her. A row that vanished
    // under «הועברה לסוף התור» would be the screen reporting the opposite of
    // what it did.
    skipQueueTicket.mockResolvedValue(list([]));
    const view = mount({ initial: list([entry({ skip_count: 1 })]) });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "דלגי — מיכל אברהם" }));
    });
    expect(skipQueueTicket).not.toHaveBeenCalled();
    expect(screen.getByText(/דילוג נוסף/)).toHaveTextContent(
      "דילוג נוסף יסיר את מיכל אברהם מהתור. להמשיך?",
    );

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "אישור ההסרה" }));
    });
    await waitFor(() => {
      expect(view.cue).toHaveBeenCalledWith({ text: "הוסרה מהתור.", name: null });
    });
    expect(skipQueueTicket).toHaveBeenCalledWith(ENTRY_A, { seen_skip_count: 1 });
  });

  it("removes only through the two-step, and the confirm NAMES her", async () => {
    // Removing a person from a queue is destructive and has no undo, and naming
    // her is what stops a manager with two «נועה»s removing by inference.
    removeQueueTicket.mockResolvedValue(list([]));
    const view = mount({ initial: list([entry({ name: "נועה בר" })]) });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — נועה בר" }));
    });
    expect(removeQueueTicket).not.toHaveBeenCalled();
    expect(screen.getByText(/להסיר את/)).toHaveTextContent("להסיר את נועה בר מהתור?");
    // A bare «אישור» is the button a hurried reader presses without reading the
    // question, on the one press with no undo.
    expect(screen.getByRole("button", { name: "אישור ההסרה" }).className).toContain("bg-danger");
    expect(screen.getByRole("button", { name: "השארה בתור" })).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "אישור ההסרה" }));
    });
    await waitFor(() => {
      expect(view.cue).toHaveBeenCalledWith({ text: "הוסרה מהתור.", name: null });
    });
    expect(removeQueueTicket).toHaveBeenCalledWith(ENTRY_A);
  });

  it("dismissing a confirm writes nothing at all", () => {
    mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "השארה בתור" }));
    });
    expect(removeQueueTicket).not.toHaveBeenCalled();
    expect(screen.queryByText(/להסיר את/)).not.toBeInTheDocument();
  });

  it("carries the Risk 2 line into the remove confirm ONLY when she is a duplicate", () => {
    // DC-6 / F-11. Whichever of her two tickets is removed, if it is the one her
    // tab polls, her phone renders «הביקור הזה הסתיים.» and stops the loop while
    // she is still in the queue on the other one. The manager is the only person
    // who can repair that, and only if she knows.
    const sentence = /אם הטלפון שלה מציג את הכניסה הזו/;
    const view = render(
      <Harness initial={list([entry({ duplicate: true })])} onCue={vi.fn()} />,
    );
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    expect(screen.getByText(sentence)).toBeInTheDocument();
    view.unmount();

    render(<Harness initial={list([entry({ duplicate: false })])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    expect(screen.queryByText(sentence)).not.toBeInTheDocument();
  });

  it("keeps ONE reveal open on the whole panel", () => {
    // Two questions on one screen is a screen that has asked the user which of
    // two irreversible acts she meant.
    mount({
      initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]),
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — נועה בר" }));
    });
    expect(screen.getByText(/להסיר את/)).toHaveTextContent("להסיר את נועה בר מהתור?");
  });
});

// --- W-vanished, W-stalecount, W-notwaiting, W-lostrace, W-outage -----------

describe("every refusal, its sentence and its register", () => {
  const refusals: [string, unknown, string][] = [
    ["a 404", new ApiError(404, "NOT_FOUND", "gone"), "הכניסה הזו כבר לא קיימת. הרשימה תתוקן בעדכון הבא."],
    [
      "a 409 naming her fitting room",
      new ApiError(409, "QUEUE_TICKET_NOT_WAITING", "…", { status: "in_service" }),
      "היא כבר בטיפול.",
    ],
    [
      "a 409 on a closed entry",
      new ApiError(409, "QUEUE_TICKET_NOT_WAITING", "…", { status: "done" }),
      "הכניסה הזו נסגרה.",
    ],
    [
      "a 409 on a removed entry",
      new ApiError(409, "QUEUE_TICKET_NOT_WAITING", "…", { status: "removed" }),
      "הכניסה הזו נסגרה.",
    ],
    [
      "a 409 with NO details",
      new ApiError(409, "QUEUE_TICKET_NOT_WAITING", "…"),
      "הכניסה הזו כבר לא ממתינה.",
    ],
    [
      "a stale skip count",
      new ApiError(409, "QUEUE_TICKET_CHANGED", "…"),
      "מצב הכניסה השתנה. הרשימה תתוקן בעדכון הבא.",
    ],
    ["a 5xx", new ApiError(500, "UNKNOWN", "…"), "לא הצלחנו לטעון את רשימת הצוות כרגע."],
  ];

  for (const [label, error, sentence] of refusals) {
    it(`renders ${label} in the row's own alert`, async () => {
      callQueueTicket.mockRejectedValue(error);
      mount({ initial: list([entry()]) });
      act(() => {
        fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
      });
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(sentence);
      expect(row(ENTRY_A).contains(alert)).toBe(true);
      // ⚠ NEVER red. Nothing that can go wrong on this surface is her fault.
      expect(alert.className).not.toContain("text-danger");
    });
  }

  it("puts the unmapped failure in the OUTAGE register and every mapped one in the NOTICE register", async () => {
    callQueueTicket.mockRejectedValue(new ApiError(500, "UNKNOWN", "…"));
    const view = render(<Harness initial={list([entry()])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    let alert = await screen.findByRole("alert");
    expect(alert.className).toContain("text-ink-muted");
    expect(alert.className).not.toContain("font-semibold");
    view.unmount();

    callQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    render(<Harness initial={list([entry()])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    alert = await screen.findByRole("alert");
    expect(alert.className).toContain("text-warning-text");
  });

  it("swaps in the PAUSED twin of every sentence that promises a next update", async () => {
    // pause() stops the loop and NOTHING else — every verb here stays fully
    // available while paused — so «הרשימה תתוקן בעדכון הבא» is then a promise
    // the screen will not keep.
    for (const [error, sentence] of [
      [new ApiError(404, "NOT_FOUND", "gone"), "הכניסה הזו כבר לא קיימת. הרשימה תתוקן עם חידוש העדכון."],
      [
        new ApiError(409, "QUEUE_TICKET_CHANGED", "…"),
        "מצב הכניסה השתנה. הרשימה תתוקן עם חידוש העדכון.",
      ],
    ] as [unknown, string][]) {
      callQueueTicket.mockRejectedValue(error);
      const view = render(<Harness initial={list([entry()])} paused onCue={vi.fn()} />);
      act(() => {
        fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
      });
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(sentence);
      view.unmount();
    }
  });

  it("REUSES F36's two shipped ROOM_OCCUPIED sentences on a push-assign", async () => {
    // ⚠ Not re-keyed into `waitlist.*`: four duplicated Hebrew values one panel
    // apart on one screen, with two floors and two `ar` guards, would drift the
    // first time anyone edited one.
    assignFromQueue.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "…", { staff_display_name: "דנה" }),
    );
    const view = render(<Harness initial={list([entry()])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });
    let alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("דנה כבר בחדר הזה.");
    // The occupant can release between the index violation and the occupant
    // read, so the unknown twin is what renders when `details` is absent.
    expect(within(alert).getByText("דנה").tagName).toBe("BDI");
    view.unmount();

    assignFromQueue.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "…"));
    render(<Harness initial={list([entry()])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });
    alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("החדר נתפס זה עתה. נסי שוב.");
  });

  it("renders the SELF form of STAFF_OCCUPIED on a push-assign, not the shipped third person", async () => {
    // DC-3. A row's push-assign carries NO target staffer, so the refusal is
    // about the caller herself and «היא כבר בחדר אחר» would name nobody on the
    // screen. The shipped third-person pair is untouched and still renders on
    // handover.
    assignFromQueue.mockRejectedValue(
      new ApiError(409, "STAFF_OCCUPIED", "…", { room_label: "חדר 5" }),
    );
    const view = render(<Harness initial={list([entry()])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });
    let alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("את כבר בחדר אחר: חדר 5.");
    expect(alert.textContent).not.toContain("היא כבר");
    view.unmount();

    assignFromQueue.mockRejectedValue(new ApiError(409, "STAFF_OCCUPIED", "…"));
    render(<Harness initial={list([entry()])} onCue={vi.fn()} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });
    alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("את כבר בחדר אחר.");
  });

  it("leaves the queue UNCHANGED after a refused verb, and writes no cue", async () => {
    // ⚠ THE RENDERED PROOF OF THE SERVER'S ROLLBACK. The woman at position 1 is
    // still at position 1 with her wait clock unbroken. If this panel ever shows
    // her gone after a refused dispatch, the transaction design failed — and it
    // is a state a manager would notice before any test would. A refusal writes
    // NO cue at all, because nothing was achieved.
    assignFromQueue.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "…"));
    const view = mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שיבוץ" }));
    });
    await screen.findByRole("alert");
    expect(within(row(ENTRY_A)).getByText("1")).toBeInTheDocument();
    expect(within(row(ENTRY_A)).getByText(/ממתינה/)).toHaveTextContent("ממתינה 23 דק'");
    expect(view.cue).not.toHaveBeenCalled();
  });

  it("keeps ONE notice-register line on a called + duplicate + refused row", async () => {
    // DC-8. On a row, --color-warning-text means "this is the answer to what you
    // just pressed", and the alert is the only LINE that carries it — which is
    // why the duplicate flag is muted rather than in the notice register.
    // (The «נקראה» Badge is a Badge, not a line: packages/ui gives the `warning`
    // variant its own colour and that is the component's business.)
    callQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount({ initial: list([entry({ called: true, duplicate: true, skip_count: 2 })]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    await screen.findByRole("alert");
    const notices = Array.from(row(ENTRY_A).querySelectorAll("p")).filter((node) =>
      node.className.includes("text-warning-text"),
    );
    expect(notices).toHaveLength(1);
    expect(notices[0]).toHaveAttribute("role", "alert");
  });

  it("clears a refusal on the next successful tick and not before", async () => {
    // The alert's own promise, kept — by the update HAPPENING and not by the
    // update DIFFERING: a tick that answers a byte-equal queue is still the
    // update that was promised.
    callQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    const view = mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    await screen.findByRole("alert");
    view.tick(list([entry()]));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

// --- the announced region ---------------------------------------------------

describe("what reaches FloorPanel's one cue", () => {
  it("writes NOTHING on a tick, however many rows appear, move or vanish", () => {
    // A status update every five seconds announces the whole queue forever and
    // makes a screen reader unusable for a whole shift. A row that appears,
    // moves or vanishes because a colleague acted — or because a woman scanned
    // the QR at the door — repaints SILENTLY. So does every renumbering.
    //
    // ⚠ Driven over SEVERAL CONSECUTIVE TICKS with the panel already populated:
    // "write" means write, not change, and a single-tick assertion passes
    // against a broken version whenever the region starts empty.
    const view = mount({ initial: list([entry()]) });
    view.tick(list([entry({ id: ENTRY_B, name: "נועה בר" }), entry({ position: 2 })]));
    view.tick(list([entry({ position: 1 })]));
    view.tick(list([]));
    view.tick(list([entry({ called: true })]));
    expect(view.cue).not.toHaveBeenCalled();
  });

  it("names the ACT in every cue and never the customer", async () => {
    // ⚠ The region is PERSISTENT — FloorPanel's <p role="status"> is overwritten
    // only by the next cue and cleared by NOTHING, not a timer, not a tick, not
    // an unmount. «נועה הוסרה מהתור.» would therefore sit in a five-role
    // screen's DOM after her row has left the payload AND after she has left the
    // shop, making the cue the only place her name survives.
    callQueueTicket.mockResolvedValue(list([entry({ called: true })]));
    skipQueueTicket.mockResolvedValue(list([entry({ skip_count: 1, position: 2 })]));
    removeQueueTicket.mockResolvedValue(list([]));
    assignFromQueue.mockResolvedValue({ room: occupied(), waitlist: list([]) });

    for (const [button, extra] of [
      ["קראי — נועה בר", null],
      ["דלגי — נועה בר", null],
      ["שבצי לחדר — נועה בר", "שיבוץ"],
      ["הסרה — נועה בר", "אישור ההסרה"],
    ] as [string, string | null][]) {
      const cue = vi.fn();
      const view = render(
        <Harness initial={list([entry({ name: "נועה בר" })])} onCue={cue} />,
      );
      act(() => {
        fireEvent.click(screen.getByRole("button", { name: button }));
      });
      if (extra !== null) {
        act(() => {
          fireEvent.click(screen.getByRole("button", { name: extra }));
        });
      }
      await waitFor(() => {
        expect(cue).toHaveBeenCalled();
      });
      for (const call of cue.mock.calls) {
        expect(call[0].text).not.toContain("נועה");
        expect(call[0].name === null || call[0].name === "חדר 1").toBe(true);
      }
      view.unmount();
    }
  });
});

// --- the six focus moves ----------------------------------------------------

describe("the six focus moves", () => {
  it("MOVE 1 — a refused verb moves focus into the row's alert", async () => {
    callQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveAttribute("tabindex", "-1");
    expect(document.activeElement).toBe(alert);
  });

  it("MOVE 2 — a success that LEAVES the row in place returns focus to its control", async () => {
    // ⚠ jsdom does NOT blur a disabled element, which is how F57 shipped a
    // VACUOUS version of this exact assertion: activeElement never became
    // <body>, the body guard never passed, and the whole restore effect could be
    // deleted with the suite green. So the tapped control is blurred explicitly
    // here, which is what a real browser does the instant `disabled` lands.
    const gate = deferred<Waitlist>();
    callQueueTicket.mockReturnValue(gate.promise);
    mount({ initial: list([entry()]) });
    const control = screen.getByRole("button", { name: "קראי — מיכל אברהם" });
    act(() => {
      control.focus();
      fireEvent.click(control);
    });
    // ⚠ AND jsdom's own blur() is a NO-OP on a DISABLED element — a disabled
    // button is not a focusable area — so the drop to <body> has to be produced
    // through a control that is still enabled. Same trap, one layer down.
    act(() => {
      const other = screen.getByRole("button", { name: "הסרה — מיכל אברהם" });
      other.focus();
      other.blur();
    });
    expect(document.activeElement).toBe(document.body);

    await act(async () => {
      gate.settle(list([entry({ called: true })]));
    });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "קראי — מיכל אברהם" }),
    );
  });

  it("MOVE 2 stands down when she moved focus somewhere else in the meantime", async () => {
    const gate = deferred<Waitlist>();
    callQueueTicket.mockReturnValue(gate.promise);
    mount({ initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    const elsewhere = screen.getByRole("button", { name: "קראי — נועה בר" });
    act(() => {
      elsewhere.focus();
    });
    await act(async () => {
      gate.settle(list([entry({ called: true }), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]));
    });
    expect(document.activeElement).toBe(elsewhere);
  });

  it("MOVE 3a — a row a TICK removes under her finger hands focus to the heading", () => {
    // ⚠ THE ISOLATING CASE for the departed arm, and it is a TICK rather than
    // her own removal: another manager dispatching her from her own device drops
    // the row with no action by this user at all. Driven through her own remove
    // instead, the outcome is ALSO delivered by MOVE 4's isConnected fallback
    // (the reveal's trigger has gone with the row), so deleting the departed arm
    // comes back green — a vacuous test wearing MOVE 3's name. Verified by
    // mutation both ways.
    const view = mount({
      initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]),
    });
    act(() => {
      screen.getByRole("button", { name: "קראי — מיכל אברהם" }).focus();
    });
    view.tick(list([entry({ id: ENTRY_B, name: "נועה בר", position: 1 })]));
    expect(screen.queryByText("מיכל אברהם")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 3 }));
  });

  it("her own removal lands on the heading too, through MOVE 4's fallback", async () => {
    // Defence in depth, stated rather than assumed: the reveal closes, its
    // trigger left with the row, `isConnected` fails and the fallback is the
    // heading. Named separately from MOVE 3a so the two mechanisms are not
    // confused for one.
    removeQueueTicket.mockResolvedValue(list([entry({ id: ENTRY_B, name: "נועה בר" })]));
    mount({ initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "אישור ההסרה" }));
    });
    await waitFor(() => {
      expect(screen.queryByText("מיכל אברהם")).not.toBeInTheDocument();
    });
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 3 }));
  });

  it("MOVE 3b — a row that TRAVELS on a successful first skip also hands focus to the heading", async () => {
    // ⚠ F-8, and the half a departing-row check alone would miss. Rows are keyed
    // by entry.id, so the row STAYS MOUNTED — now at position 40, below the
    // fold, where a focus ring is indistinguishable from lost focus for exactly
    // the user who most needs it. Declined the alternative of re-focusing the
    // moved control, which scrolls it into view: a forty-row scroll jump with no
    // user action is the repaint F34's F-8 exists to prevent, and the cue
    // already says what happened.
    //
    // ⚠⚠ THE BLUR IS THE WHOLE TEST, and its first version did not have it —
    // which made this assertion VACUOUS in precisely the way MOVE 2's comment
    // twenty lines up warns about, on the very next test down. A first skip is
    // the ONE path with no reveal, so `loading` lands on the TAPPED control and
    // a real browser blurs it the instant `disabled` does; by the time the
    // response swaps the list, `document.activeElement` is <body> and the DOM
    // can no longer say which row she was in. jsdom keeps focus on the disabled
    // button instead, so the travelled arm resolved a row it could never resolve
    // in Chromium and the assertion passed while MOVE 2 — not MOVE 3 — did the
    // work, scrolling the page forty rows down to the moved control. Verified by
    // mutation: with the click-time capture in `act` removed, this test reds and
    // focus lands on «קראי — מיכל אברהם» at position 2.
    const travelled = list([
      entry({ id: ENTRY_B, name: "נועה בר", position: 1 }),
      entry({ skip_count: 1, position: 2 }),
    ]);
    const gate = deferred<Waitlist>();
    skipQueueTicket.mockReturnValue(gate.promise);
    mount({ initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]) });
    const control = screen.getByRole("button", { name: "דלגי — מיכל אברהם" });
    act(() => {
      control.focus();
      fireEvent.click(control);
    });
    // The drop to <body>, produced through a still-enabled control because
    // jsdom's own blur() is a no-op on a disabled one. MOVE 2's trap, one test
    // down, for the same reason.
    act(() => {
      const other = screen.getByRole("button", { name: "הסרה — מיכל אברהם" });
      other.focus();
      other.blur();
    });
    expect(document.activeElement).toBe(document.body);

    await act(async () => {
      gate.settle(travelled);
    });
    await waitFor(() => {
      expect(within(row(ENTRY_A)).getByText("2")).toBeInTheDocument();
    });
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 3 }));
  });

  it("MOVE 3b stands down when she moved focus OFF the panel while the skip was in flight", async () => {
    // The other side of the click-time capture, and the reason it is consulted
    // ONLY when activeElement is <body>. The capture says where she WAS, not
    // where she is: if she has since put focus on something real — FloorPanel's
    // «השהיה» sits directly above this panel and is the likeliest — then a
    // rescue would be MOVE 3 doing the exact stealing MOVE 2's own stand-down
    // guard exists to prevent, one move over. The plain button stands for that
    // control, which this harness deliberately does not mount.
    const travelled = list([
      entry({ id: ENTRY_B, name: "נועה בר", position: 1 }),
      entry({ skip_count: 1, position: 2 }),
    ]);
    const gate = deferred<Waitlist>();
    skipQueueTicket.mockReturnValue(gate.promise);
    mount({ initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]) });
    const control = screen.getByRole("button", { name: "דלגי — מיכל אברהם" });
    act(() => {
      control.focus();
      fireEvent.click(control);
    });
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    act(() => {
      outside.focus();
    });

    await act(async () => {
      gate.settle(travelled);
    });
    await waitFor(() => {
      expect(within(row(ENTRY_A)).getByText("2")).toBeInTheDocument();
    });
    expect(document.activeElement).toBe(outside);
    outside.remove();
  });

  it("MOVE 3c — a colleague's renumbering under her finger does NOT steal focus", async () => {
    // The other side of the same rule: a row that moves because SOMEBODY ELSE
    // acted repaints silently, and yanking focus to the heading on every remote
    // renumber would be worse than the bug it fixes.
    const view = mount({
      initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]),
    });
    const control = screen.getByRole("button", { name: "קראי — נועה בר" });
    act(() => {
      control.focus();
    });
    view.tick(list([entry({ id: ENTRY_B, name: "נועה בר", position: 1 })]));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "קראי — נועה בר" }));
  });

  it("MOVE 3d — a row that leaves WITH A REVEAL OPEN still lands on the heading", () => {
    // The third of the plan's three deletions. Here MOVE 5's open-capture is
    // what puts focus inside the row in the first place, so deleting THAT reds
    // this case; the departed arm and MOVE 4's fallback then both point at the
    // heading, which is why the outcome survives either one alone.
    const view = mount({ initial: list([entry(), entry({ id: ENTRY_B, name: "נועה בר", position: 2 })]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    // Focus is inside the reveal, which is inside the row.
    expect(row(ENTRY_A).contains(document.activeElement)).toBe(true);
    view.tick(list([entry({ id: ENTRY_B, name: "נועה בר", position: 1 })]));
    expect(screen.queryByText(/להסיר את/)).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 3 }));
  });

  it("MOVE 4 — dismissing a reveal returns focus to its trigger", () => {
    mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    act(() => {
      const dismiss = screen.getByRole("button", { name: "השארה בתור" });
      dismiss.focus();
      fireEvent.click(dismiss);
      document.body.focus();
    });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "הסרה — מיכל אברהם" }),
    );
  });

  it("MOVE 4 — a tick that takes the LAST FREE ROOM closes the assign reveal and rescues focus", () => {
    // F-9, reached by a tick instead of a tap, and it costs no seventh
    // mechanism: the trigger is now gone too, so `isConnected` fails and the
    // fallback lands on the heading. An option-less <select> is a dead control
    // that looks live and a disabled one is banned outright.
    const view = mount({ initial: list([entry()]), rooms: [room()] });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    expect(screen.getByLabelText("שיבוץ לחדר — מיכל אברהם")).toBeInTheDocument();
    view.tick(undefined, [occupied()]);
    expect(screen.queryByLabelText("שיבוץ לחדר — מיכל אברהם")).not.toBeInTheDocument();
    expect(screen.getByText("אין חדר פנוי כרגע.")).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 3 }));
  });

  it("MOVE 5 — a reveal that opens puts focus on the QUESTION, and the assign one on the Select", () => {
    mount({ initial: list([entry({ skip_count: 1 })]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    expect(document.activeElement).toBe(screen.getByText(/להסיר את/));
    expect(document.activeElement).toHaveTextContent("להסיר את מיכל אברהם מהתור?");
    expect(document.activeElement).toHaveAttribute("tabindex", "-1");

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "דלגי — מיכל אברהם" }));
    });
    expect(document.activeElement).toHaveTextContent(
      "דילוג נוסף יסיר את מיכל אברהם מהתור. להמשיך?",
    );

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — מיכל אברהם" }));
    });
    expect(document.activeElement).toBe(screen.getByLabelText("שיבוץ לחדר — מיכל אברהם"));
  });

  it("MOVE 6 — a tick that clears a FOCUSED alert hands focus back to the row's control", async () => {
    // ~5s after the refusal, with NO USER ACTION. «הרשימה תתוקן בעדכון הבא» is
    // kept by this tick, and focus must not fall to <body> with the alert —
    // her next Tab would restart at the skip link.
    callQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    const view = mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    const alert = await screen.findByRole("alert");
    expect(document.activeElement).toBe(alert);
    view.tick(list([entry()]));
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "קראי — מיכל אברהם" }),
    );
  });

  it("a refusal focuses the ALERT and not the reveal's trigger, when both settle in one commit", async () => {
    // The collision, resolved explicitly: setRowError and setOpenReveal(null)
    // land together, and the [rowError] effect is declared BEFORE the
    // [openReveal] one — so MOVE 1 focuses the alert and MOVE 4 then finds
    // activeElement off <body> and stands down.
    removeQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount({ initial: list([entry()]) });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "הסרה — מיכל אברהם" }));
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "אישור ההסרה" }));
    });
    const alert = await screen.findByRole("alert");
    expect(document.activeElement).toBe(alert);
    // And the reveal is GONE: a refused verb answers in the alert, and leaving
    // an open question beside it would be two things asking at once.
    expect(screen.queryByText(/להסיר את/)).not.toBeInTheDocument();
  });
});

// --- axe, explicitly not sufficient -----------------------------------------

describe("axe", () => {
  it("returns zero violations over a fully populated panel", async () => {
    // ⚠ EXPLICITLY NOT THE COVERAGE. axe cannot see a focus move that never
    // happened (four shipped instances in this repo), it has NO rule for SC
    // 2.2.2, and it computes contrast against declared colours rather than
    // composited pixels. The six moves above and the shipped pause tests are
    // where those three classes live.
    callQueueTicket.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount({
      initial: list(
        [
          entry({ called: true, duplicate: true, skip_count: 1 }),
          entry({ id: ENTRY_B, name: "נועה בר", position: 2, visit_type: "evening", arrived_at: ARRIVED_JUST }),
        ],
        true,
      ),
      rooms: [room(), room({ id: ROOM_B, label: "חדר 2" })],
    });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "קראי — מיכל אברהם" }));
    });
    await screen.findByRole("alert");
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "שבצי לחדר — נועה בר" }));
    });

    const results = await run(document.body, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
