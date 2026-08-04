import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../i18n";
import type { SosAlert } from "../api";
import { GuideOverlay } from "../components/GuideOverlay";
import { GUIDE_STEPS, type SectionKey } from "../lib/guide";
import { SosProvider, SOS_INTERVAL_MS } from "../lib/sos";

/**
 * ⚠ NO TEST IN THIS FILE ASSERTS FOCUS, AND THAT IS A RULE RATHER THAN AN
 * OVERSIGHT (spec DL17).
 *
 * jsdom 29.1.1 ships no `<dialog>` implementation — the impl file is an empty
 * subclass — so `src/test/setup.ts` stubs BOTH `showModal` and `show` with a
 * body that is literally `this.open = true`. No focus move, no trap, no top
 * layer, no `cancel` event on Esc. A vitest assertion about the dialog's focus,
 * its Tab cycle or its Esc route would therefore measure the stub, and would
 * stay green with the component's focus code deleted.
 *
 * Every focus criterion of this feature lives in `e2e/guide.spec.ts`, in real
 * Chromium, each with the named deletion that reddens it. §7 below is the one
 * permitted exception: it is a plain IDREF read with no focus and no `<dialog>`
 * behaviour in it.
 */

// The fourteen are SPELLED OUT here, re-derived from `App.tsx:24-41` by hand on
// 2026-08-04, rather than imported from `SectionKey` or read back off
// `GUIDE_STEPS`: a test that derives its expectation from the thing under test
// proves nothing. A fifteenth section arriving must fail HERE as well as at the
// typecheck.
const SECTIONS = [
  "dashboard",
  "profile",
  "hours",
  "types",
  "terms",
  "catalog",
  "bookings",
  "customers",
  "board",
  "staff",
  "gateway",
  "floor",
  "checkinQr",
  "atelier",
  // F20, the fifteenth. Spelled out rather than derived, which is the whole
  // point of this list: `i18n.test.ts` derives ITS walk from `GUIDE_STEPS`, so
  // if this one derived too, a section added to the union with no steps could
  // never be caught by either.
  "privacy",
];

/**
 * ⚠ THE HARNESS MOUNTS INSIDE `<SosProvider>` BECAUSE `useSos()` THROWS OUTSIDE
 * IT — «Loud rather than inert» (`lib/sos-context.ts:32-40`), the same warning
 * four shipped test files carry. It copies `SosCentre.test.tsx`'s shape rather
 * than inventing one, and it deliberately does NOT `vi.mock("../lib/sos-context")`:
 * that is one line shorter and it stubs the exact mechanism the SOS-close test
 * exists to measure — the provider's array identity across a poll tick.
 */
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    FALLBACK_ERROR_MESSAGE: actual.FALLBACK_ERROR_MESSAGE,
    api: {
      getSos: vi.fn(),
      raiseSos: vi.fn(),
      acceptSos: vi.fn(),
      resolveSos: vi.fn(),
      cancelSos: vi.fn(),
    },
  };
});

const { api } = await import("../api");
const getSos = vi.mocked(api.getSos);

const NOW = "2026-08-04T11:07:00Z";
const RAISED_AT = "2026-08-04T11:04:00Z";
// A distinct id, so a second page is NAMED by the failure rather than counted.
const SECOND_ID = "bbbbbbbb-0000-0000-0000-00000000000b";

function alert(overrides: Partial<SosAlert> = {}): SosAlert {
  return {
    id: "aaaaaaaa-0000-0000-0000-00000000000a",
    status: "open",
    raised_by: "11111111-1111-1111-1111-111111111111",
    raised_by_name: "נועה לוי",
    target_staff_user_id: null,
    target_name: null,
    room_label: null,
    note: null,
    accepted_by: null,
    accepted_by_name: null,
    acknowledged_at: null,
    created_at: RAISED_AT,
    escalated: false,
    stalled: false,
    for_me: true,
    ...overrides,
  };
}

function sosPayload(alerts: SosAlert[]) {
  return { alerts, server_now: NOW };
}

function mount(section: SectionKey = "floor") {
  return render(
    <SosProvider>
      <GuideOverlay section={section} />
    </SosProvider>,
  );
}

function tree(section: SectionKey) {
  return (
    <SosProvider>
      <GuideOverlay section={section} />
    </SosProvider>
  );
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function trigger(): HTMLElement {
  return screen.getByRole("button", { name: i18n.t("guide.trigger") });
}

// ⚠ AN ATTRIBUTE READ, NOT A ROLE QUERY. A CLOSED `<dialog>` is a jsdom grey
// area — the element exists, `Modal` renders its children unconditionally, and
// `getByRole` must not be trusted for it. `dialog[open]` is also the selector
// `SosOverlay.tsx:298` itself uses.
function dialogEl(): HTMLDialogElement {
  const node = document.querySelector("dialog");
  if (!(node instanceof HTMLDialogElement)) throw new Error("no dialog rendered");
  return node;
}

function isOpen(): boolean {
  return dialogEl().hasAttribute("open");
}

function region(): HTMLElement {
  return screen.getByRole("status");
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getSos.mockReset();
  getSos.mockResolvedValue(sosPayload([]));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the step table", () => {
  it("covers every section, by set equality", () => {
    expect(new Set(Object.keys(GUIDE_STEPS))).toEqual(new Set(SECTIONS));
  });

  it("gives every section at least one step", () => {
    // The type already makes an empty tuple unrepresentable (spec DL4); this is
    // the runtime twin, and it is what catches a section whose steps were
    // emptied through a cast.
    //
    // Widened to `readonly string[]` deliberately, the same move the shipped
    // `ar` empty-string guard makes: with the literal tuple types `as const`
    // gives, tsc types `.length` as `2 | 3`, calls the comparison unreachable
    // and fails the typecheck — so the guard would have to be deleted the day
    // it was needed.
    const empty = Object.entries<readonly string[]>(GUIDE_STEPS).filter(
      ([, steps]) => steps.length === 0,
    );
    expect(empty).toEqual([]);
  });
});

describe("the guide shows the section she is looking at", () => {
  it("renders the active section's steps and no other section's", async () => {
    mount("floor");
    fireEvent.click(trigger());

    const panel = within(dialogEl());
    expect(panel.getByText(i18n.t("guide.floor.1"))).toBeInTheDocument();
    // AC6. The role gate is structural — `activeKey` (App.tsx:208-210) is
    // already the role-filtered truth — so a receptionist can only ever be
    // OFFERED `floor`, and F60 re-implements no filter.
    expect(panel.queryByText(i18n.t("guide.dashboard.1"))).toBeNull();
    expect(panel.getByText(i18n.t("guide.title", { section: i18n.t("nav.floor") }))).toBeInTheDocument();
  });
});

describe("it never opens itself", () => {
  it("stays shut through three poll ticks, with a for_me page live and without one", async () => {
    // AC7 / DL16. `open` is set true in exactly one place — the trigger's
    // onClick. There is no effect, no timer, no storage read and no first-visit
    // branch anywhere in this feature: an overlay that opened itself would steal
    // focus from a receptionist mid-phone-number.
    getSos.mockResolvedValue(sosPayload([alert()]));
    mount("floor");
    await advance(SOS_INTERVAL_MS * 3);
    expect(isOpen()).toBe(false);

    getSos.mockResolvedValue(sosPayload([]));
    await advance(SOS_INTERVAL_MS * 3);
    expect(isOpen()).toBe(false);

    fireEvent.click(trigger());
    expect(isOpen()).toBe(true);
  });
});

describe("the step controls", () => {
  it("carries a dismiss on every step, hides «הקודם» on step 1, and ends on «סיום»", async () => {
    mount("floor"); // three steps
    fireEvent.click(trigger());
    const panel = within(dialogEl());

    // AC19 — the ONLY pointer route out. `Modal` binds no backdrop click and the
    // chrome has no X, so without this a keyboard-less tablet can leave step 1
    // only by tapping through to the end.
    expect(panel.getByRole("button", { name: i18n.t("guide.close") })).toBeInTheDocument();
    // ABSENT, not disabled (DL10): inside a trap every Tab stop is one she must
    // walk past, and `Button.tsx:57` is `disabled={disabled || loading}`, which
    // blurs a tapped control and drops focus.
    expect(panel.queryByRole("button", { name: i18n.t("guide.prev") })).toBeNull();
    expect(panel.getByRole("button", { name: i18n.t("guide.next") })).toBeInTheDocument();

    fireEvent.click(panel.getByRole("button", { name: i18n.t("guide.next") }));
    expect(panel.getByRole("button", { name: i18n.t("guide.prev") })).toBeInTheDocument();
    expect(panel.getByText(i18n.t("guide.floor.2"))).toBeInTheDocument();

    fireEvent.click(panel.getByRole("button", { name: i18n.t("guide.next") }));
    expect(panel.queryByRole("button", { name: i18n.t("guide.next") })).toBeNull();
    expect(panel.getByRole("button", { name: i18n.t("guide.done") })).toBeInTheDocument();
    // Still there on the last step — «סיום» says «you have reached the end» and
    // «סגירה» says «leave»; the two sit side by side and must differ.
    expect(panel.getByRole("button", { name: i18n.t("guide.close") })).toBeInTheDocument();

    fireEvent.click(panel.getByRole("button", { name: i18n.t("guide.done") }));
    expect(isOpen()).toBe(false);
  });

  it("leaves from step 1 by «סגירה» alone", async () => {
    mount("floor");
    fireEvent.click(trigger());
    fireEvent.click(within(dialogEl()).getByRole("button", { name: i18n.t("guide.close") }));
    expect(isOpen()).toBe(false);
  });
});

describe("the live region", () => {
  it("is empty on every open, speaks on every change, and never carries a stale sentence", async () => {
    const view = render(tree("floor"));
    fireEvent.click(trigger());
    const panel = within(dialogEl());

    // Silent on open: the step is announced by aria-describedby, and a live
    // region freshly exposed WITH content is announced by some ATs and not
    // others. Unreliable is worse than silent.
    expect(region().textContent).toBe("");

    fireEvent.click(panel.getByRole("button", { name: i18n.t("guide.next") }));
    expect(region().textContent).toBe(
      `${i18n.t("guide.progress", { step: 2, total: 3 })} · ${i18n.t("guide.floor.2")}`,
    );

    // Going BACK announces, and that is correct rather than an oversight: the
    // region carries whatever the last `index` change produced.
    fireEvent.click(panel.getByRole("button", { name: i18n.t("guide.prev") }));
    expect(region().textContent).toBe(
      `${i18n.t("guide.progress", { step: 1, total: 3 })} · ${i18n.t("guide.floor.1")}`,
    );

    // ⚠ THE ONLY LEG THAT FAILS IF `setAnnounced("")` IS MISSING FROM THE
    // TRIGGER'S onClick. The first leg above is true on a session's first open
    // regardless, because the region has never held anything. `Modal` never
    // unmounts its children, so without the clear the region still holds the
    // PREVIOUS section's last sentence and transitions from display:none to
    // exposed carrying it.
    fireEvent.click(panel.getByRole("button", { name: i18n.t("guide.close") }));
    view.rerender(tree("board"));
    fireEvent.click(trigger());
    expect(region().textContent).toBe("");
  });
});

describe("an SOS page closes the guide", () => {
  // ⚠ THE ONLY WAY THIS FEATURE CAN HURT ANYBODY, which is why it is four
  // separate legs rather than one. `showModal()` promotes the dialog to the
  // browser's TOP LAYER, which paints above every z-index in the document —
  // including SosOverlay's `z-40` (:451) — and makes every node outside the
  // dialog INERT. With the guide open, an arriving emergency page is not merely
  // covered, it is UNANSWERABLE, and there is no z-index, no portal and no
  // stacking context that changes that. Closing the guide is the only mechanism
  // that exists.

  it("closes when a for_me page arrives", async () => {
    mount("floor");
    await advance(SOS_INTERVAL_MS);
    fireEvent.click(trigger());
    expect(isOpen()).toBe(true);

    getSos.mockResolvedValue(sosPayload([alert()]));
    await advance(SOS_INTERVAL_MS);
    expect(isOpen()).toBe(false);
  });

  it("stays out of the way of a page that is NOT for_me", async () => {
    // Deck §5.4. The channel-down strip and the «N hidden» affordance are not
    // full-screen, are not urgent, and closing a walkthrough for them would be
    // noise. This is the only test that dies if the `for_me` filter is dropped.
    mount("floor");
    await advance(SOS_INTERVAL_MS);
    fireEvent.click(trigger());

    getSos.mockResolvedValue(sosPayload([alert({ for_me: false })]));
    await advance(SOS_INTERVAL_MS);
    expect(isOpen()).toBe(true);
  });

  it("reopens over a page that is still live — the close is EDGE-triggered, never level", async () => {
    // ⚠ AC10 / DL12. Dismissal is deliberate and per-device
    // (`SosOverlay:322-330`), so a level-triggered guard would close the guide
    // for as long as a live-but-dismissed alert existed — a staffer who
    // dismissed a page could never open it again.
    //
    // ⚠ THE MUTATION THAT REDDENS THIS IS A LEVEL CHECK THAT ACTUALLY RUNS —
    // `keys.length > 0` with the dependency array DROPPED. Swapping the set
    // difference for `keys.length > 0` while `[risingKey]` stays comes back
    // GREEN, and that is the point rather than a gap: the dependency array is
    // itself an edge on the alert list, so the two guards compose. Verified by
    // running both.
    getSos.mockResolvedValue(sosPayload([alert()]));
    mount("floor");
    await advance(SOS_INTERVAL_MS);

    fireEvent.click(trigger());
    expect(isOpen()).toBe(true);
    await advance(SOS_INTERVAL_MS * 3);
    expect(isOpen()).toBe(true);
  });

  it("closes when a SECOND page arrives beside a live one — appended at the END", async () => {
    // ⚠ FAILS AGAINST ANY HEAD-OF-LIST DETECTOR. `alerts` is oldest-first on
    // every path — `sos-context.ts:18` declares it, `sos_alerts.py:245` is
    // `ORDER BY created_at` ascending, and `sos.tsx:128-131` appends — so a new
    // page lands at the END. That is precisely the case where a top-layer dialog
    // is most dangerous: the second emergency arrives under a dialog the first
    // one already failed to close.
    const first = alert();
    getSos.mockResolvedValue(sosPayload([first]));
    mount("floor");
    await advance(SOS_INTERVAL_MS);

    fireEvent.click(trigger());
    expect(isOpen()).toBe(true);

    getSos.mockResolvedValue(sosPayload([first, alert({ id: SECOND_ID })]));
    await advance(SOS_INTERVAL_MS);
    expect(isOpen()).toBe(false);
  });

  it("closes when an already-seen page RE-RISES because `escalated` flipped", async () => {
    // ⚠ FAILS AGAINST ANY ID-ONLY DETECTOR, and it is not §6c with different
    // words. `SosOverlay.dismissKey` (:59-61) is composite PRECISELY because
    // escalation at t=30s and the stall at t=2min each re-rise a dismissed card
    // exactly once — F37's safety net for «the first responder did not come».
    // An id-keyed detector is structurally blind to exactly the alert this guard
    // exists for.
    getSos.mockResolvedValue(sosPayload([alert()]));
    mount("floor");
    await advance(SOS_INTERVAL_MS);

    fireEvent.click(trigger());
    expect(isOpen()).toBe(true);

    getSos.mockResolvedValue(sosPayload([alert({ escalated: true })]));
    await advance(SOS_INTERVAL_MS);
    expect(isOpen()).toBe(false);
  });
});

// --- axe ------------------------------------------------------------------------

describe("axe", () => {
  it("passes with zero violations over the open dialog", async () => {
    // Every console component's test file runs this pass and this one is no
    // exception — a new `Modal` caller with a new IDREF is exactly the shape
    // `aria-valid-attr-value` exists for.
    //
    // ⚠ IT IS THE FLOOR AND NOT THE PROOF. axe reports NONE of the focus class
    // this feature is actually about, and it was green all five times this repo
    // shipped a focus-drops-to-<body> defect. The proof is `e2e/guide.spec.ts`,
    // in Chromium.
    const { container } = mount("floor");
    fireEvent.click(trigger());

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});

describe("aria-describedby", () => {
  it("points at the element carrying the current step", async () => {
    // AC5, and ⚠ THE ONE PERMITTED EXCEPTION TO DL17: a plain IDREF read, with
    // no focus and no <dialog> behaviour in it. Without it the whole of D3 could
    // be dropped at build time and every other test in this file would stay
    // green — `showModal()` puts focus on the first control, so with
    // aria-labelledby alone a screen-reader user hears the dialog's name and a
    // button label and never hears the step.
    mount("floor");
    fireEvent.click(trigger());

    const describedBy = screen.getByRole("dialog").getAttribute("aria-describedby");
    expect(typeof describedBy).toBe("string");
    expect(document.getElementById(describedBy ?? "")?.textContent).toBe(i18n.t("guide.floor.1"));
  });
});
