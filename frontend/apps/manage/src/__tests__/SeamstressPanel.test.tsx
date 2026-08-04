import { fireEvent, render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { describe, expect, it, vi } from "vitest";
import "../i18n";
import i18n from "../i18n";
import type { SeamstressRef } from "../api";
import { SeamstressPanel } from "../components/SeamstressPanel";

// The panel is rendered DIRECTLY here. It owns no poll, no timer and no
// announced region — AtelierSection owns all three — so everything below is
// reachable with the props the section hands it. The harness is a stub of the
// POLL, not of any mechanism under test.

const DANA = "11111111-1111-1111-1111-111111111111";
const RUTI = "22222222-2222-2222-2222-222222222222";
const NOA = "33333333-3333-3333-3333-333333333333";

// The server's horizon, off the wire. ⚠ The test script pins
// TZ=America/New_York; this date never meets a `Date` and never meets a
// formatter, which is `plainDate`'s whole rule and the reason F-1 put the field
// on the envelope instead of computing `today + 7` in the browser.
const THROUGH = "2026-08-11";
// ⚠ RENDERED BY `plainDate` — d.m.yyyy, «11.8.2026» — and NOT by
// `plainDayMonth`. The decks' worked rows are sketched as «עד 11.8», which is
// the narrow d.m spelling the dashboard's week rows use because their year
// lives once per panel in a range line. This panel has no range line, so the
// year would have no home, and the plan and the copy deck both name `plainDate`
// — the one date spelling the boutique reads product-wide, including in the SMS
// the bride already gets.
const THROUGH_RENDERED = "11.8.2026";

function seamstress(overrides: Partial<SeamstressRef> = {}): SeamstressRef {
  return {
    id: DANA,
    display_name: "דנה",
    assignable: true,
    weekly_capacity_hours: null,
    capacity_is_default: false,
    assigned_minutes: 0,
    due_soon_minutes: 0,
    ...overrides,
  };
}

// 12 h = 720 min. Every row below is measured against it.
const CONFIGURED = { weekly_capacity_hours: 12 } as const;

function mount(
  props: {
    seamstresses?: SeamstressRef[];
    unassignedMinutes?: number;
    role?: string;
    onDialogOpenChange?: (open: boolean) => void;
  } = {},
) {
  return render(
    // ⚠ dir="rtl" is the console's own frame (index.html:2 is
    // `<html lang="he" dir="rtl">`), reproduced here because this feature's
    // headline widget FILLS FROM THE INLINE-START EDGE — the physical RIGHT.
    <div dir="rtl">
      <main>
        <h1 className="sr-only">ניהול הבוטיק</h1>
        <SeamstressPanel
          seamstresses={props.seamstresses ?? [seamstress()]}
          unassignedMinutes={props.unassignedMinutes ?? 0}
          dueSoonThrough={THROUGH}
          role={props.role ?? "owner"}
          onDialogOpenChange={props.onDialogOpenChange ?? (() => {})}
        />
      </main>
    </div>,
  );
}

function list(): HTMLElement {
  return screen.getByRole("list", { name: i18n.t("atelier.capacity.heading") });
}

function rowOf(name: string): HTMLElement {
  return screen.getByText(name).closest("li") as HTMLElement;
}

// The bar is aria-hidden, so no ARIA query can reach it. It is addressed
// structurally, which is also what the "no widget semantics" test needs.
function barOf(name: string): HTMLElement | null {
  return rowOf(name).querySelector("[aria-hidden='true']");
}

function fillOf(name: string): HTMLElement {
  const bar = barOf(name);
  expect(bar).not.toBeNull();
  return (bar as HTMLElement).firstElementChild as HTMLElement;
}

describe("structure — one named region, one named list, and the names differ", () => {
  it("exposes the section as a region and the list under the UNCOUNTED name", () => {
    // An unnamed <section> is not exposed as a region at all and an unnamed
    // <ul> is an anonymous list — a user navigating by list would land on six
    // consecutive unnamed lists and have no way to tell the capacity panel from
    // the `qc` column.
    //
    // ⚠ The <ul> takes the UNCOUNTED name and that is not a style choice: an
    // accessible name must not churn on a five-second tick, and this count CAN
    // change with no staff edit — `seamstresses` is a union, so a retired
    // assignee leaves it the moment her last undelivered ticket is delivered.
    //
    // Asking for role="list" BY NAME also catches a row grid built with
    // role="grid", which D8 refuses structurally.
    mount({ seamstresses: [seamstress()] });
    expect(screen.getByRole("region", { name: /תופרות/ })).toBeTruthy();
    expect(list()).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("תופרות · 1");
  });

  it("counts PEOPLE in the heading and keeps the unassigned total OUT of the list", () => {
    // ⚠ With the unassigned line inside the <ul>, a screen-reader user would
    // hear «תופרות, 4 פריטים» after a heading claiming 3, on every board with
    // unassigned work. Outside, the list's item count and the heading's number
    // are the same fact.
    const rows = [
      seamstress({ id: DANA, display_name: "דנה", ...CONFIGURED, due_soon_minutes: 360 }),
      seamstress({ id: RUTI, display_name: "רותי" }),
      seamstress({ id: NOA, display_name: "נועה", ...CONFIGURED, due_soon_minutes: 900 }),
    ];
    mount({ seamstresses: rows, unassignedMinutes: 240 });

    expect(within(list()).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("תופרות · 3");
    expect(screen.getByText("לא משויך · 4 שעות")).toBeTruthy();
    expect(within(list()).queryByText(/לא משויך/)).toBeNull();
  });

  it("renders the rows in remaining-capacity order and not alphabetically", () => {
    // דנה (+6 h), רותי (unknown), נועה (over). Alphabetically it would be
    // דנה, נועה, רותי — the panel is not alphabetical, and the overloaded
    // seamstress is LAST rather than ranked above a colleague nobody has
    // configured.
    const rows = [
      seamstress({ id: NOA, display_name: "נועה", ...CONFIGURED, due_soon_minutes: 900 }),
      seamstress({ id: RUTI, display_name: "רותי", assigned_minutes: 240 }),
      seamstress({ id: DANA, display_name: "דנה", ...CONFIGURED, due_soon_minutes: 360 }),
    ];
    mount({ seamstresses: rows });
    // Read off the row's own id rather than its text: the text is the whole
    // announced sentence, and slicing it would make this assertion depend on
    // the copy it is not testing.
    expect(
      within(list())
        .getAllByRole("listitem")
        .map((item) => item.getAttribute("data-seamstress-id")),
    ).toEqual([DANA, RUTI, NOA]);
  });

  it("adds no dir attribute of its own, anywhere in the panel", () => {
    // ⚠ THE MIRRORED-PANEL GUARD. The bar fills from the inline-start edge,
    // which under the console's dir="rtl" is the physical RIGHT. That is
    // `dir="rtl"`'s doing, not the logical property's — so ANY dir attribute
    // introduced inside this tree (a `dir="ltr"` reached for around a numeral,
    // say) flips the fill for the rows below it, passes axe, passes every named
    // assertion here, and reads backwards to the only users who see it.
    mount({ seamstresses: [seamstress({ ...CONFIGURED, due_soon_minutes: 432 })] });
    expect(screen.getByRole("region", { name: /תופרות/ }).querySelectorAll("[dir]")).toHaveLength(0);
  });
});

describe("the bar", () => {
  it("carries NO widget semantics at all", () => {
    // ⚠ A BARE COLOURED DIV IS A FAIL AND SO IS A role="progressbar" BOLTED
    // ONTO ONE. Both are refused. ARIA's progressbar is the progress of a TASK;
    // a capacity meter is a LEVEL, and an AT would read it as an in-flight
    // operation. The honest form would then need aria-valuetext — byte-identical
    // to the visible sentence beside it, putting one fact in the accessibility
    // tree twice.
    //
    // ⚠ AND AXE CANNOT CATCH THIS. It has no rule that fires on a CORRECTLY
    // FORMED progressbar in the wrong place; it would pass
    // role="progressbar" aria-valuenow="125" without complaint. This assertion
    // is the only thing standing between the deck and that build.
    mount({ seamstresses: [seamstress({ ...CONFIGURED, due_soon_minutes: 432 })] });
    const bar = barOf("דנה") as HTMLElement;
    expect(bar.getAttribute("aria-hidden")).toBe("true");
    for (const attribute of [
      "role",
      "aria-valuenow",
      "aria-valuemin",
      "aria-valuemax",
      "aria-valuetext",
      "aria-label",
      "aria-labelledby",
      "title",
    ]) {
      expect(bar.getAttribute(attribute)).toBeNull();
      expect(fillOf("דנה").getAttribute(attribute)).toBeNull();
    }
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByRole("meter")).toBeNull();
  });

  it("sizes the fill with inline-size and NEVER with width", () => {
    // The one spelling of one widget, kept verbatim from the shipped Bar. It is
    // the form that stays correct if a writing mode ever changes, and swapping
    // it for `width` is the change a reviewer reaches for when they meet a
    // mirrored bar — which is never the cause.
    mount({ seamstresses: [seamstress({ ...CONFIGURED, due_soon_minutes: 432 })] });
    const fill = fillOf("דנה");
    expect(fill.style.inlineSize).toBe("60%");
    expect(fill.style.width).toBe("");
  });

  it("paints with DECLARED tokens — gold when calm, danger when over", () => {
    // ⚠ NEVER bg-accent. theme.css's @theme declares fourteen colours and no
    // `accent`; Tailwind 4 emits no utility for an undeclared token, so an
    // accent fill would leave this feature's headline widget INVISIBLE IN ITS
    // NORMAL STATE and visible only when it is red.
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "דנה", ...CONFIGURED, due_soon_minutes: 432 }),
        seamstress({ id: NOA, display_name: "נועה", ...CONFIGURED, due_soon_minutes: 900 }),
      ],
    });
    expect(fillOf("דנה").className).toContain("bg-gold-strong");
    expect(fillOf("נועה").className).toContain("bg-danger");
    for (const name of ["דנה", "נועה"]) {
      expect(fillOf(name).className).not.toContain("bg-accent");
      expect((barOf(name) as HTMLElement).className).toContain("bg-border");
    }
  });

  it("draws 0 %, 100 %, 140 % and 400 % — and 140 and 400 are byte-identical", () => {
    // Past 100 % only the colour and the NUMBERS IN THE SENTENCE move. The
    // width answers how full, the colour answers over or not, and the text
    // answers by how much. Asserted so nobody adds a stripe, an overflow nub or
    // a «×4» chip to an aria-hidden widget to "show the excess".
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "אפס", ...CONFIGURED, due_soon_minutes: 0 }),
        seamstress({ id: RUTI, display_name: "מלאה", ...CONFIGURED, due_soon_minutes: 720 }),
        seamstress({ id: NOA, display_name: "מאה", ...CONFIGURED, due_soon_minutes: 1008 }),
        seamstress({
          id: "44444444-4444-4444-4444-444444444444",
          display_name: "ארבע",
          ...CONFIGURED,
          due_soon_minutes: 2880,
        }),
      ],
    });
    expect(fillOf("אפס").style.inlineSize).toBe("0%");
    expect(fillOf("מלאה").style.inlineSize).toBe("100%");
    expect(fillOf("מאה").outerHTML).toBe(fillOf("ארבע").outerHTML);
    // ⚠ AT EXACTLY 100 % THE BAR IS FULL AND GOLD. `overloaded` is strictly
    // `>`, and full-and-calm is the honest rendering of a seamstress with
    // exactly a week of work in a week. The colour flips one minute later with
    // NO width change at all.
    expect(fillOf("מלאה").className).toContain("bg-gold-strong");
    expect(rowOf("מלאה").textContent).not.toContain("עומס יתר");
  });

  it("draws a TRACK for zero capacity and NOTHING AT ALL for null", () => {
    // ⚠ Opposite states, and the difference must be visible without reading: an
    // empty track says "she has room and holds nothing"; no track says "nobody
    // has told this product how much she can take."
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "אפס", weekly_capacity_hours: 0 }),
        seamstress({ id: RUTI, display_name: "ריק" }),
      ],
    });
    expect(barOf("אפס")).not.toBeNull();
    expect(barOf("ריק")).toBeNull();
  });
});

describe("the row's sentence — the entire accessibility payload of the bar", () => {
  it("states the horizoned load, the horizon date and her capacity", () => {
    // ⚠ The date comes off the WIRE. The server filtered on its own
    // today_jerusalem + 7, lib/jerusalem.ts ships no date arithmetic, and a
    // device that has crossed Jerusalem midnight would print a horizon the SQL
    // did not use.
    mount({
      seamstresses: [seamstress({ ...CONFIGURED, due_soon_minutes: 360, assigned_minutes: 360 })],
    });
    expect(rowOf("דנה").textContent).toContain(`6 שעות עד ${THROUGH_RENDERED} מתוך 12`);
  });

  it("carries the WORD on an overloaded row, and both numbers with it", () => {
    // ⚠ THE NAMED MUTATION: delete «עומס יתר» and keep the red class → red.
    // For a sighted user the bar turning red is the signal; for a screen-reader
    // user, and for anyone in greyscale or forced colours, THESE TWO WORDS ARE
    // THE OVERLOAD.
    mount({
      seamstresses: [
        seamstress({
          display_name: "נועה",
          ...CONFIGURED,
          due_soon_minutes: 900,
          assigned_minutes: 2760,
        }),
      ],
    });
    const text = rowOf("נועה").textContent ?? "";
    expect(text).toContain("נועה");
    expect(text).toContain(`15 שעות עד ${THROUGH_RENDERED} מתוך 12`);
    expect(text).toContain("עומס יתר");
    expect(text).toContain("סה״כ 46 שעות בתור");
  });

  it("carries the word as ONE announced sentence, never a second Badge", () => {
    // F41 fixes exactly one Badge per card and overdue owns it, and this panel
    // sits three inches above sixty of those cards. A Badge here would also
    // split the payload into two announced chunks, where the whole point is
    // that the row reads as one continuous sentence.
    //
    // The non-colour half is the weight: `text-danger` on `bg-surface` is
    // 6.18:1, so the word passes AA as text on its own, and `font-semibold`
    // survives greyscale.
    mount({
      seamstresses: [seamstress({ display_name: "נועה", ...CONFIGURED, due_soon_minutes: 900 })],
    });
    const word = within(rowOf("נועה")).getByText("עומס יתר");
    expect(word.tagName).toBe("STRONG");
    expect(word.className).toContain("font-semibold");
    expect(word.className).toContain("text-danger");
    expect(word.closest("p")).toBe(within(rowOf("נועה")).getByText(/מתוך 12/).closest("p"));
  });

  it("renders NO bar and «לא הוגדרה קיבולת» for a seamstress with no capacity", () => {
    // ⚠ THE SINGLE MOST LIKELY STATE IN WEEK ONE, and it must not read as an
    // error. The load is true data and always renders; only the bar is
    // withheld, because a bar without a denominator is a picture of a number
    // that does not exist.
    //
    // ⚠ And `{{hours}}` here is her WHOLE BACKLOG, not the seven-day slice —
    // which is what makes an unconfigured row comparable with a configured
    // one's «בתור» clause.
    mount({
      seamstresses: [
        seamstress({ display_name: "רותי", assigned_minutes: 240, due_soon_minutes: 60 }),
      ],
    });
    expect(barOf("רותי")).toBeNull();
    const text = rowOf("רותי").textContent ?? "";
    expect(text).toContain("4 שעות");
    expect(text).toContain("לא הוגדרה קיבולת");
    expect(text).not.toContain("עומס יתר");
    expect(text).not.toContain("מתוך");
  });

  it("names WHOSE the number is when it was inherited, and never otherwise", () => {
    // A manager reallocating work must know whether 30 is a fact about this
    // seamstress or a fact about the shop. Last clause, because it qualifies
    // the denominator rather than saying whether there is a problem.
    mount({
      seamstresses: [
        seamstress({
          id: DANA,
          display_name: "דנה",
          ...CONFIGURED,
          capacity_is_default: true,
          due_soon_minutes: 360,
        }),
        seamstress({ id: RUTI, display_name: "רותי", ...CONFIGURED, due_soon_minutes: 360 }),
      ],
    });
    expect(rowOf("דנה").textContent).toContain("ברירת מחדל של הבוטיק");
    expect(rowOf("רותי").textContent).not.toContain("ברירת מחדל של הבוטיק");
  });

  it("states the queue only when the bar's week is hiding some of it", () => {
    // «סה״כ … בתור» exists so the total is never hidden behind the seven-day
    // slice. When the slice IS the total, nothing is hidden and the clause
    // states the same number twice — which is why none of the deck's five bar
    // renderings carries it and the worked row (360 due, 720 held) does.
    mount({
      seamstresses: [
        seamstress({
          id: DANA,
          display_name: "דנה",
          ...CONFIGURED,
          due_soon_minutes: 360,
          assigned_minutes: 720,
        }),
        seamstress({
          id: RUTI,
          display_name: "רותי",
          ...CONFIGURED,
          due_soon_minutes: 360,
          assigned_minutes: 360,
        }),
      ],
    });
    expect(rowOf("דנה").textContent).toContain("סה״כ 12 שעות בתור");
    expect(rowOf("רותי").textContent).not.toContain("בתור");
  });

  it("rounds the rendered hours UP so they never read equal beside the word", () => {
    // 721 minutes against 12 h: with Math.round the row would say «12 שעות …
    // מתוך 12 · עומס יתר» — displayed numbers saying EQUAL beside a word saying
    // OVER, in the one string that is this feature's whole a11y payload.
    mount({
      seamstresses: [seamstress({ display_name: "נועה", ...CONFIGURED, due_soon_minutes: 721 })],
    });
    const text = rowOf("נועה").textContent ?? "";
    expect(text).toContain(`12.1 שעות עד ${THROUGH_RENDERED} מתוך 12`);
    expect(text).toContain("עומס יתר");
  });
});

describe("the write controls — role-gated, and the gate is not cosmetics", () => {
  it("renders «שעות» per row and «הגדרות» once, for an elevated viewer", () => {
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "דנה" }),
        seamstress({ id: RUTI, display_name: "רותי" }),
      ],
      role: "shift_manager",
    });
    expect(screen.getAllByRole("button", { name: /^שעות/ })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^הגדרות/ })).toHaveLength(1);
    // Per-row accessible names, because a six-row panel otherwise exposes six
    // buttons all named «שעות» and a screen-reader user pulling up the control
    // list cannot address one.
    expect(screen.getByRole("button", { name: "שעות — דנה" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "שעות — רותי" })).toBeTruthy();
  });

  it("renders NO control at all for a seamstress", () => {
    // ⚠ NOT A DEAD BUTTON — THE WHOLE BOARD. She is admitted to the board by
    // the router and refused by both write routes, so a control she can tap
    // produces a 403 → runMutation's catch → poll.fail → usePoll's {401,403}
    // terminal rule → her entire atelier board is replaced by «אין הרשאה»,
    // because she tapped something this console offered her.
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "דנה" }),
        seamstress({ id: RUTI, display_name: "רותי" }),
      ],
      role: "seamstress",
    });
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    // And she loses NOTHING else: every row, every bar and every sentence.
    expect(within(list()).getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders no «שעות» on a row the server would refuse", () => {
    // `_require_seamstress` refuses a retired or re-roled staffer, so the
    // control would always 400. Her LOAD still renders — the work is real and
    // somebody must move it — and she carries the shipped «תופרת שאינה פעילה».
    mount({
      seamstresses: [
        seamstress({
          id: NOA,
          display_name: "נועה",
          assignable: false,
          ...CONFIGURED,
          due_soon_minutes: 900,
          assigned_minutes: 2760,
        }),
        seamstress({ id: DANA, display_name: "דנה" }),
      ],
    });
    expect(within(rowOf("נועה")).queryAllByRole("button")).toHaveLength(0);
    expect(rowOf("נועה").textContent).toContain("תופרת שאינה פעילה");
    expect(rowOf("נועה").textContent).toContain(`15 שעות עד ${THROUGH_RENDERED} מתוך 12`);
    expect(barOf("נועה")).not.toBeNull();
    // The gate is per row, not per panel.
    expect(within(rowOf("דנה")).getAllByRole("button")).toHaveLength(1);
  });

  it("reports its dialog state upward and calls nothing else on a tap", () => {
    // ⚠ The signal exists for one reason: AtelierSection's deferred terminal
    // gates on `dialogOpen`, and without it a 401 tick unmounts a settings
    // dialog holding six edited band values. The trigger OPENS; the confirm
    // writes.
    const onDialogOpenChange = vi.fn();
    mount({ onDialogOpenChange });
    onDialogOpenChange.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "שעות — דנה" }));
    expect(onDialogOpenChange).toHaveBeenCalledWith(true);
  });

  it("keeps every control at the 44 px floor", () => {
    // `Button size="md"` is min-h-11; `size="sm"` is 36 px and is barred
    // anywhere in this tree, because axe has no target-size rule at the level
    // this repo runs it. ⚠ Scoped to the Button and not to the Input: the
    // shipped Input lands at 43.6 px by this repo's own type scale, and a check
    // written >= 44 would red against a packages/ui component F42 may not edit
    // — while WCAG 2.0 AA, the legal bar here, has no target-size criterion at
    // all.
    mount({ seamstresses: [seamstress()] });
    for (const button of screen.getAllByRole("button")) {
      expect(button.className).toContain("min-h-11");
      expect(button.className).not.toContain("min-h-9");
    }
    expect(
      screen.getByRole("region", { name: /תופרות/ }).querySelectorAll("[class*='min-h-9']"),
    ).toHaveLength(0);
  });
});

describe("the four empty states", () => {
  it("tells an OWNER where to add staff and tells nobody else", () => {
    // ⚠ TWO STRINGS, NOT ONE. The staff screen is owner-only, and a line
    // telling a shift manager to go somewhere the gate refuses is this console
    // lying about its own permissions.
    const { unmount } = mount({ seamstresses: [], role: "owner" });
    expect(screen.getByText("אין תופרות רשומות. אפשר להוסיף במסך הצוות.")).toBeTruthy();
    unmount();

    mount({ seamstresses: [], role: "shift_manager" });
    expect(screen.getByText("אין תופרות רשומות.")).toBeTruthy();
    expect(screen.queryByText(/במסך הצוות/)).toBeNull();
  });

  it("still offers the boutique-wide ruler when there is nobody yet", () => {
    // The default is worth setting before the first hire, and the heading still
    // counts — «תופרות · 0» rather than a missing panel.
    mount({ seamstresses: [], role: "owner" });
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("תופרות · 0");
    expect(screen.getByRole("button", { name: /^הגדרות/ })).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("renders the empty line AND the unassigned line, in that order", () => {
    // A boutique that opens three tickets before adding any staff satisfies
    // both rules at once — a plausible first hour of a pilot — and it is the
    // state in which the unassigned total is the ONLY TRUE THING on the panel.
    mount({ seamstresses: [], unassignedMinutes: 240, role: "shift_manager" });
    const empty = screen.getByText("אין תופרות רשומות.");
    const unassigned = screen.getByText("לא משויך · 4 שעות");
    expect(empty.compareDocumentPosition(unassigned) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("renders no unassigned line at all when nothing is unassigned", () => {
    // A zero line is noise on every board that is fully assigned.
    mount({ seamstresses: [seamstress()], unassignedMinutes: 0 });
    expect(screen.queryByText(/לא משויך/)).toBeNull();
  });

  it("renders every row with its real load and no bar when nothing is configured", () => {
    // The SECOND thing a new boutique sees. «הגדרות» (one boutique-wide
    // default) and each row's «שעות» (one person) are both one tap away.
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "דנה", assigned_minutes: 360 }),
        seamstress({ id: RUTI, display_name: "רותי", assigned_minutes: 120 }),
      ],
    });
    for (const name of ["דנה", "רותי"]) {
      expect(barOf(name)).toBeNull();
      expect(rowOf(name).textContent).toContain("לא הוגדרה קיבולת");
    }
    expect(rowOf("דנה").textContent).toContain("6 שעות");
    expect(rowOf("רותי").textContent).toContain("2 שעות");
  });

  it("renders «0 שעות» for a configured seamstress on a board with no tickets", () => {
    // The FIRST thing a brand-new boutique sees, and the branch a zero-ticket
    // board is in: setting capacity before the first intake is the useful
    // order.
    mount({ seamstresses: [seamstress({ ...CONFIGURED })], unassignedMinutes: 0 });
    expect(rowOf("דנה").textContent).toContain(`0 שעות עד ${THROUGH_RENDERED} מתוך 12`);
    expect(fillOf("דנה").style.inlineSize).toBe("0%");
  });
});

describe("the list is bounded at ≥768 only, and is a tab stop at every width", () => {
  it("is unbounded at 375 and 24 rem above it", () => {
    // ⚠ Bounding at 375 reintroduces the scroll-trap F41 refused on the primary
    // device: at that width column bodies are not height-bounded and the page
    // scrolls naturally. And 16 rem — the spec's first number — is 2.3 common
    // rows, not the four it claimed: the estimate omitted the 44 px button row
    // the touch-target floor makes mandatory.
    mount({ seamstresses: [seamstress()] });
    expect(list().className).toContain("md:max-h-96");
    expect(list().className).toContain("md:overflow-y-auto");
    expect(list().className).not.toMatch(/(^|\s)max-h-/);
  });

  it("is focusable unconditionally", () => {
    // axe's scrollable-region-focusable fires on exactly this shape, and a
    // resize observer deciding an ARIA-relevant attribute is a mechanism to
    // keep true for a tab stop that costs nothing. It is also the keyboard's
    // entry stop into the list.
    mount({ seamstresses: [seamstress()] });
    expect(list().getAttribute("tabindex")).toBe("0");
    // The heading is a TARGET, not a stop.
    expect(screen.getByRole("heading", { level: 3 }).getAttribute("tabindex")).toBe("-1");
  });
});

describe("axe — explicitly not sufficient", () => {
  it("finds no violation on a panel carrying every rendering at once", async () => {
    // ⚠ NOT THE COVERAGE. axe cannot see a bar that fills from the wrong edge,
    // a missing «עומס יתר» beside a red class, or a role="progressbar" that is
    // correctly formed and wrong. Every one of those has its own assertion
    // above.
    mount({
      seamstresses: [
        seamstress({ id: DANA, display_name: "דנה", ...CONFIGURED, due_soon_minutes: 360 }),
        seamstress({ id: RUTI, display_name: "רותי", assigned_minutes: 240 }),
        seamstress({
          id: NOA,
          display_name: "נועה",
          ...CONFIGURED,
          due_soon_minutes: 900,
          assigned_minutes: 2760,
        }),
      ],
      unassignedMinutes: 240,
    });
    const results = await run(document.body, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
