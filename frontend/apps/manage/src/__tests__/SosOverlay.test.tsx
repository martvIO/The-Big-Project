import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { Modal, ToastProvider } from "@boutique/ui";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { SosAlert } from "../api";
import { SosOverlay } from "../components/SosOverlay";
import { SosProvider } from "../lib/sos";

/**
 * THE HARDEST A11Y SURFACE IN THIS PRODUCT, because it appears UNBIDDEN.
 *
 * ⚠ TWO TRAPS MAKE A FOCUS TEST HERE VACUOUS AND BOTH HAVE SHIPPED IN THIS REPO.
 *
 *   1. jsdom does not blur a disabled element. `Button` is
 *      `disabled={disabled || loading}`, so a REAL browser blurs the tapped
 *      control the instant a request starts — and every action in this feature
 *      is that shape. F57's shipped note records that its own success-path focus
 *      test was therefore vacuous: activeElement never became <body>, the guard
 *      never passed, and the whole restore effect could be deleted with the
 *      suite green. Every focus test below either blurs explicitly or asserts a
 *      destination that cannot be reached by accident.
 *   2. A test asserting «focus moved to X» CANNOT FAIL when focus is stolen from
 *      somewhere it should not have been. So AC14 is three separate assertions,
 *      each with its own delete-the-guard mutation, and the steal direction has
 *      its own tests (AC14 a/c, MOVE D's negative, MOVE B/C's negative).
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

const { api, ApiError } = await import("../api");
const getSos = vi.mocked(api.getSos);
const acceptSos = vi.mocked(api.acceptSos);

// 08:20Z is 11:20 in Jerusalem (IDT, UTC+3) and 04:20 in New York — and the test
// script pins TZ=America/New_York, so an unzoned read prints 04:20 and «מאז
// 11:20» fails loudly rather than quietly.
const RAISED_AT = "2026-08-04T08:20:00Z";
const LATER_AT = "2026-08-04T08:24:00Z";
const NOW = "2026-08-04T08:25:00Z";

const ALERT_A = "aaaaaaaa-0000-0000-0000-00000000000a";
const ALERT_B = "bbbbbbbb-0000-0000-0000-00000000000b";

function alertRow(overrides: Partial<SosAlert> = {}): SosAlert {
  return {
    id: ALERT_A,
    status: "open",
    raised_by: "11111111-1111-1111-1111-111111111111",
    raised_by_name: "דנה כהן",
    target_staff_user_id: null,
    target_name: null,
    room_label: "חדר 2",
    note: "צריך סיכות",
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

function page(alerts: SosAlert[]) {
  return { alerts, server_now: NOW };
}

// The overlay is mounted the way `App` mounts it: BEFORE the console's <main>,
// so its controls precede every other focusable in DOM order — and #console-main
// exists, because MOVE B lands there and never on <body>.
function mount(extra?: React.ReactNode) {
  return render(
    <ToastProvider>
      <SosProvider>
        <SosOverlay />
        <main id="console-main" tabIndex={-1}>
          <button type="button">ניווט</button>
          <input aria-label="טלפון" defaultValue="050" />
          {extra}
        </main>
      </SosProvider>
    </ToastProvider>,
  );
}

function cards(): HTMLElement[] {
  return Array.from(document.querySelectorAll("[data-alert-id]"));
}

function card(id: string): HTMLElement {
  const node = document.querySelector(`[data-alert-id="${id}"]`);
  if (!(node instanceof HTMLElement)) {
    throw new Error(`no card for ${id}`);
  }
  return node;
}

function acceptControl(id: string): HTMLElement {
  return within(card(id)).getByRole("button", { name: /אני מגיעה/ });
}

async function settle() {
  await act(async () => {
    await Promise.resolve();
  });
}

/**
 * ⚠ THE ONLY WAY TO REACH `<body>` IN jsdom AFTER A CONTROL GOES `disabled`.
 *
 * `Button` is `disabled={disabled || loading}`, so Chromium blurs the tapped
 * control the instant the request starts and `document.activeElement` becomes
 * `<body>` BEFORE the response lands. jsdom does neither half of that: it does
 * not blur on disable, and `HTMLElement.blur()` BAILS OUT on an element that is
 * not a focusable area — a disabled button is not one — so the `control.blur()`
 * this file uses elsewhere is a NO-OP on a disabled control and any test that
 * relies on it to produce `<body>` is vacuous. Measured, not assumed: an earlier
 * draft asserted `activeElement === document.body` straight after
 * `accept.blur()` and FAILED with activeElement still the disabled button.
 *
 * A scratch node outside React's tree is focusable, so blurring THAT really does
 * land on `<body>`.
 */
function dropFocusToBody() {
  const scratch = document.createElement("button");
  document.body.appendChild(scratch);
  scratch.focus();
  scratch.blur();
  scratch.remove();
}

function deferAccept(): (alert: SosAlert) => void {
  let settleAccept: (alert: SosAlert) => void = () => {};
  acceptSos.mockReturnValue(
    new Promise<SosAlert>((resolve) => {
      settleAccept = resolve;
    }),
  );
  return (alert) => settleAccept(alert);
}

const ACCEPTED = () =>
  alertRow({ status: "accepted", accepted_by_name: "רותם", for_me: false });

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getSos.mockReset();
  acceptSos.mockReset();
  getSos.mockResolvedValue(page([]));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// --- S-none, S-quiet, and the card's four lines ------------------------------

describe("what renders, and the normal state is nothing", () => {
  it("renders NOTHING at all when there are no alerts", async () => {
    mount();
    await settle();

    expect(cards()).toHaveLength(0);
    expect(screen.queryByRole("alert")).toBeNull();
    // No landmark, no region, no tab stop — 100% of the time.
    expect(document.querySelector(".bg-danger")).toBeNull();
  });

  it("renders NOTHING when alerts exist but none is for_me — a DIFFERENT state, same render", async () => {
    // A shift manager watching a seamstress-to-seamstress page in its first
    // thirty seconds. This is what stops her being interrupted by every page in
    // the boutique and learning within a day to dismiss them unread.
    getSos.mockResolvedValue(page([alertRow({ for_me: false })]));
    mount();
    await settle();

    expect(cards()).toHaveLength(0);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("puts who, where and the note in ONE role=alert region, with the absolute raise time OUTSIDE it", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    const region = within(card(ALERT_A)).getByRole("alert");
    expect(region).toHaveTextContent("דנה כהן קוראת לעזרה");
    expect(region).toHaveTextContent("חדר 2");
    expect(region).toHaveTextContent("צריך סיכות");
    // ⚠ The WHEN is a SIBLING. Inside, aria-atomic would re-announce the card.
    expect(region).not.toHaveTextContent("מאז");
    expect(card(ALERT_A)).toHaveTextContent("מאז 11:20");
  });

  it("carries DC-4's visually-hidden location prefix INSIDE the region, before the bare room label", async () => {
    // `CreateRoomRequest.label` carries no Field bound and 0019 puts no CHECK on
    // content, so a boutique that types «2» is fully supported — and the atomic
    // utterance would otherwise be «דנה כהן קוראת לעזרה 2 צריך סיכות».
    getSos.mockResolvedValue(page([alertRow({ room_label: "2" })]));
    mount();
    await screen.findByText("2");

    const region = within(card(ALERT_A)).getByRole("alert");
    expect(region).toHaveTextContent("מיקום");
    expect(region.querySelector(".sr-only")).toHaveTextContent("מיקום");
    // NOT an aria-label on the <p>: ARIA prohibits naming role=paragraph.
    expect(region.querySelector("p[aria-label]")).toBeNull();
  });

  it("names a removed raiser and a missing room, and OMITS the note element entirely when it is null", async () => {
    getSos.mockResolvedValue(
      page([alertRow({ raised_by_name: null, room_label: null, note: null })]),
    );
    mount();
    await screen.findByText(/אשת צוות שאינה ברשימה/);

    const region = within(card(ALERT_A)).getByRole("alert");
    expect(region).toHaveTextContent("אשת צוות שאינה ברשימה קוראת לעזרה");
    expect(region).toHaveTextContent("לא בחדר מדידה");
    // ABSENT, never an empty line: three block children, not four.
    expect(region.querySelectorAll("p")).toHaveLength(2);
  });

  it("renders one card per rising alert, OLDEST FIRST, whatever order they arrive in", async () => {
    getSos.mockResolvedValue(
      page([
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
        alertRow({ id: ALERT_A, created_at: RAISED_AT }),
      ]),
    );
    mount();
    await screen.findByText("נועה לוי");

    expect(cards().map((node) => node.getAttribute("data-alert-id"))).toEqual([
      ALERT_A,
      ALERT_B,
    ]);
  });

  it("puts «אני מגיעה» FIRST in the card's DOM and «הסתרה» after it", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    const buttons = within(card(ALERT_A)).getAllByRole("button");
    expect(buttons[0]).toHaveTextContent("אני מגיעה");
    expect(buttons[1]).toHaveTextContent("הסתרה");
    // WCAG 2.5.3: each accessible name STARTS with its visible label.
    expect(buttons[0]).toHaveAccessibleName("אני מגיעה — הקריאה מדנה כהן");
    expect(buttons[1]).toHaveAccessibleName("הסתרה — הקריאה מדנה כהן");
  });
});

// --- AC16: the region is WRITE-ONCE ------------------------------------------

describe("AC16 — the role=alert element's text is byte-identical from mount to unmount", () => {
  it("does not change across three consecutive ticks NOR across escalation and stall", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    const region = within(card(ALERT_A)).getByRole("alert");
    const announced = region.textContent;

    getSos.mockResolvedValue(page([alertRow({ escalated: true })]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    await screen.findByText("ללא מענה");
    expect(within(card(ALERT_A)).getByRole("alert").textContent).toBe(
      announced,
    );

    getSos.mockResolvedValue(
      page([alertRow({ status: "accepted", escalated: false, stalled: true })]),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await screen.findByText("אין תזוזה מאז שאושרה");
    expect(within(card(ALERT_A)).getByRole("alert").textContent).toBe(
      announced,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(within(card(ALERT_A)).getByRole("alert").textContent).toBe(
      announced,
    );
    // The escalation clause is a SIBLING: still on the card, outside the region.
    expect(card(ALERT_A)).toHaveTextContent("אין תזוזה מאז שאושרה");
  });

  it("mounts a SECOND role=alert for a second page and does not touch the first", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const first = within(card(ALERT_A)).getByRole("alert");
    const announced = first.textContent;

    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await screen.findByText("נועה לוי");

    // One region PER CARD and never one wrapping the list: with a wrapper,
    // aria-atomic re-announces every card and the seamstress hears again about
    // the emergency she already answered.
    expect(screen.getAllByRole("alert")).toHaveLength(2);
    expect(within(card(ALERT_A)).getByRole("alert")).toBe(first);
    expect(first.textContent).toBe(announced);
  });
});

// --- AC14: THE OVERLAY DOES NOT STEAL FOCUS ----------------------------------

describe("AC14 — the overlay does not steal focus, in all three branches", () => {
  it("(a) leaves a caret in a text input alone — value intact, AND still announces", async () => {
    mount();
    await settle();
    const field = screen.getByLabelText("טלפון") as HTMLInputElement;
    field.focus();
    fireEvent.change(field, { target: { value: "0501234567" } });

    getSos.mockResolvedValue(page([alertRow()]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    await screen.findByText("דנה כהן");

    expect(document.activeElement).toBe(field);
    expect(field.value).toBe("0501234567");
    // The alert is STILL announced: role="alert" interrupts a screen reader
    // WITHOUT taking focus, which is the whole reason that role exists.
    expect(within(card(ALERT_A)).getByRole("alert")).toHaveTextContent(
      "דנה כהן קוראת לעזרה",
    );
  });

  it("(b) moves focus to the CARD CONTAINER when nothing holds it — never to the accept control", async () => {
    // DC-1. MOVE A fires iff activeElement === <body> — precisely the state in
    // which the next Space is a page scroll — so landing on «אני מגיעה» would
    // convert that keypress into an IRREVERSIBLE accept sitting on top of the
    // two-minute stall hole. Accept stays first in DOM, so reach costs one Tab.
    mount();
    await settle();
    expect(document.activeElement).toBe(document.body);

    getSos.mockResolvedValue(page([alertRow()]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    await screen.findByText("דנה כהן");

    expect(document.activeElement).toBe(card(ALERT_A));
    expect(document.activeElement?.tagName).toBe("ARTICLE");
    expect(document.activeElement?.tagName).not.toBe("BUTTON");
    // …and it is NAMED, so an AT does not re-read the whole subtree the alert
    // just announced.
    expect(card(ALERT_A)).toHaveAccessibleName("דנה כהן קוראת לעזרה");
  });

  it("(c) leaves a nav button alone — the ORDINARY state of a console in use", async () => {
    mount();
    await settle();
    const nav = screen.getByRole("button", { name: "ניווט" });
    nav.focus();

    getSos.mockResolvedValue(page([alertRow()]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    await screen.findByText("דנה כהן");

    expect(document.activeElement).toBe(nav);
    expect(within(card(ALERT_A)).getByRole("alert")).toHaveTextContent(
      "דנה כהן קוראת לעזרה",
    );
  });

  it("does NOT move focus for a SECOND card arriving while the first overlay is open", async () => {
    // MOVE A is «the first rising alert appears», not «any alert appears». A
    // second page grabbing focus would move it out from under a reader who is
    // mid-sentence on the emergency she is already answering.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const accept = acceptControl(ALERT_A);
    accept.focus();

    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await screen.findByText("נועה לוי");

    expect(document.activeElement).toBe(accept);
  });

  it("does NOT move focus for a second card even when NOTHING holds focus by then", async () => {
    // ⚠ THIS BLOCK EXISTS BECAUSE THE MUTATION CAME BACK GREEN WITHOUT IT.
    // Deleting MOVE A's «first card only» check left the whole suite passing:
    // every other arrival test has focus somewhere, so the === document.body
    // guard was doing all the work and the `had` check was pinned by nothing.
    //
    // The reachable case is the red field itself. It is deliberately inert, so
    // a tap on it puts activeElement on <body> — and a second page arriving a
    // moment later must still not move focus onto the FIRST card, which is not
    // the one that just arrived and not where she was looking.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    // ⚠ WAIT FOR MOVE A TO HAVE LANDED BEFORE BLURRING. `findByText` waits for
    // DOM TEXT; MOVE A happens in a passive effect that may not have flushed
    // yet, and blurring `<body>` is a no-op — so under load the precondition
    // silently failed to hold, MOVE A then fired on the FIRST card, and this
    // test reddened with «expected <article> to be <body>». Measured: 2 failures
    // in 10 `make fe-test` runs on the unmodified tree.
    await waitFor(() => expect(document.activeElement).toBe(card(ALERT_A)));
    (document.activeElement as HTMLElement | null)?.blur();
    expect(document.activeElement).toBe(document.body);

    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await screen.findByText("נועה לוי");

    expect(document.activeElement).toBe(document.body);
  });
});

// --- AC15: MOVE B, MOVE C, MOVE D -------------------------------------------

describe("AC15 — MOVE B, MOVE C and MOVE D", () => {
  it("MOVE B — the overlay leaving while holding focus lands on #console-main, never <body>", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }).focus();

    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );

    await waitFor(() => expect(cards()).toHaveLength(0));
    expect(document.activeElement).toBe(
      document.getElementById("console-main"),
    );
    expect(document.activeElement).not.toBe(document.body);
  });

  it("MOVE C — a card leaving with siblings remaining lands on the NEXT CARD'S CONTAINER, not its button", async () => {
    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    mount();
    await screen.findByText("נועה לוי");
    within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }).focus();

    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );

    await waitFor(() => expect(cards()).toHaveLength(1));
    // DC-1 again, and it is WORSE here than on arrival: parking focus on a
    // DIFFERENT emergency's accept control at the moment the user was
    // mid-keyboard-interaction with the one that left.
    expect(document.activeElement).toBe(card(ALERT_B));
    expect(document.activeElement?.tagName).toBe("ARTICLE");
  });

  it("does NOT move focus when a card leaves and focus was never inside it", async () => {
    // The steal direction. A test asserting «focus moved to X» cannot fail when
    // focus is taken from somewhere it should not have been.
    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    mount();
    await screen.findByText("נועה לוי");
    const field = screen.getByLabelText("טלפון") as HTMLInputElement;
    field.focus();

    getSos.mockResolvedValue(
      page([
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await waitFor(() => expect(cards()).toHaveLength(1));

    expect(document.activeElement).toBe(field);
  });

  it("MOVE D — a 409's in-card alert takes focus when she tapped THAT card's accept", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const accept = acceptControl(ALERT_A);
    accept.focus();
    acceptSos.mockRejectedValue(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken", {
        staff_display_name: "נועה לוי",
      }),
    );

    fireEvent.click(accept);
    // ⚠ EXPLICIT BLUR. `Button` is disabled={disabled||loading}, so a real
    // browser blurs it here — jsdom does not, and F57's equivalent test was
    // vacuous for exactly this reason.
    accept.blur();
    await waitFor(() =>
      expect(card(ALERT_A)).toHaveTextContent("נועה לוי כבר מגיעה."),
    );

    const alerts = within(card(ALERT_A)).getAllByRole("alert");
    // ⚠ `waitFor`, for the reason above: the text landing and MOVE D running are
    // two different moments. NOT vacuous — delete the effect and focus stays on
    // the (still-focused, because jsdom does not blur it) accept control, so this
    // times out and reds.
    await waitFor(() =>
      expect(document.activeElement).toBe(alerts[alerts.length - 1]),
    );
  });

  it("MOVE D's guard — a 409 landing while she types BEHIND the overlay does not pull her out", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const accept = acceptControl(ALERT_A);
    let settleAccept: (value: never) => void = () => {};
    acceptSos.mockReturnValue(
      new Promise((_resolve, reject) => {
        settleAccept = reject as (value: never) => void;
      }),
    );

    fireEvent.click(accept);
    accept.blur();
    const field = screen.getByLabelText("טלפון") as HTMLInputElement;
    field.focus();
    fireEvent.change(field, { target: { value: "0509999999" } });

    await act(async () => {
      settleAccept(
        new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken", {
          staff_display_name: "נועה לוי",
        }) as never,
      );
      await Promise.resolve();
    });
    await waitFor(() =>
      expect(card(ALERT_A)).toHaveTextContent("נועה לוי כבר מגיעה."),
    );

    expect(document.activeElement).toBe(field);
    expect(field.value).toBe("0509999999");
  });
});

// --- MOVE B and MOVE C on the path that actually happens: a SUCCESSFUL accept -

describe("MOVE B and MOVE C after a SUCCESSFUL accept — the path a real browser takes", () => {
  it("MOVE B — an accept that empties the overlay lands on #console-main, never <body>", async () => {
    // ⚠ THE ONLY MOVE B/C TESTS THIS FILE HAD DROVE «הסתרה», which is a
    // synchronous ghost Button that is NEVER `disabled` — so focus genuinely
    // stays on it in BOTH engines, the intent is captured, and the tests pass
    // over a path Chromium never takes. On the real path the tapped control goes
    // `disabled` mid-flight, the browser blurs it to <body>, and the render that
    // drops the card reads <body>: `focusedCardId()` is null, so the departing
    // intent was never set and MOVE B never ran. Spec AC15 says «Never <body>».
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const accept = acceptControl(ALERT_A);
    accept.focus();
    const land = deferAccept();

    fireEvent.click(accept);
    expect(accept).toBeDisabled();
    dropFocusToBody();
    expect(document.activeElement).toBe(document.body);

    await act(async () => {
      land(ACCEPTED());
      await Promise.resolve();
    });
    await waitFor(() => expect(cards()).toHaveLength(0));

    await waitFor(() =>
      expect(document.activeElement).toBe(
        document.getElementById("console-main"),
      ),
    );
    expect(document.activeElement).not.toBe(document.body);
  });

  it("MOVE C — an accept with a sibling emergency still up lands on the NEXT CARD'S CONTAINER", async () => {
    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    mount();
    await screen.findByText("נועה לוי");
    const accept = acceptControl(ALERT_A);
    accept.focus();
    const land = deferAccept();

    fireEvent.click(accept);
    dropFocusToBody();

    await act(async () => {
      land(ACCEPTED());
      await Promise.resolve();
    });
    await waitFor(() => expect(cards()).toHaveLength(1));

    await waitFor(() => expect(document.activeElement).toBe(card(ALERT_B)));
    expect(document.activeElement?.tagName).toBe("ARTICLE");
  });

  it("the STEAL direction — an accept settling while she has moved on does NOT yank her back", async () => {
    // ⚠ F41's post-mortem, applied. Its first fix stopped focus being dropped
    // and introduced a focus STEAL instead. The fallback that makes MOVE B fire
    // is «she acted on this card AND nothing holds focus»; drop the second
    // conjunct — `focusedCardId() ?? actedRef.current` — and this reds, because
    // `actedRef` is still her card and the guard above it cannot tell the
    // difference.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const accept = acceptControl(ALERT_A);
    accept.focus();
    const land = deferAccept();

    fireEvent.click(accept);
    // She went back to work while the request was in the air.
    const field = screen.getByLabelText("טלפון") as HTMLInputElement;
    field.focus();
    fireEvent.change(field, { target: { value: "0509999999" } });

    await act(async () => {
      land(ACCEPTED());
      await Promise.resolve();
    });
    await waitFor(() => expect(cards()).toHaveLength(0));
    // …and settle, so a steal firing one flush LATE is caught rather than raced.
    await settle();

    expect(document.activeElement).toBe(field);
    expect(field.value).toBe("0509999999");
  });
});

// --- the accept's own outcomes ------------------------------------------------

describe("the accept, and every sentence its refusals can carry", () => {
  it("fires ONE request on a double tap and disables the control in flight", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    acceptSos.mockReturnValue(new Promise(() => {}));

    const accept = acceptControl(ALERT_A);
    fireEvent.click(accept);
    fireEvent.click(accept);
    await settle();

    expect(acceptSos).toHaveBeenCalledTimes(1);
    expect(acceptControl(ALERT_A)).toBeDisabled();
  });

  it("names the owner from `details`, and admits it does not know when `details` is absent", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    acceptSos.mockRejectedValueOnce(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken"),
    );
    fireEvent.click(acceptControl(ALERT_A));
    await waitFor(() =>
      expect(card(ALERT_A)).toHaveTextContent("מישהי אחרת כבר מגיעה."),
    );

    acceptSos.mockRejectedValueOnce(new ApiError(409, "SOS_CLOSED", "closed"));
    fireEvent.click(acceptControl(ALERT_A));
    await waitFor(() =>
      expect(card(ALERT_A)).toHaveTextContent("הקריאה כבר נסגרה."),
    );

    acceptSos.mockRejectedValueOnce(new ApiError(404, "NOT_FOUND", "gone"));
    fireEvent.click(acceptControl(ALERT_A));
    await waitFor(() =>
      expect(card(ALERT_A)).toHaveTextContent("הקריאה כבר לא פתוחה."),
    );
    // A 404 is NOT terminal: the card is still there and the loop still runs.
    expect(cards()).toHaveLength(1);

    acceptSos.mockRejectedValueOnce(new Error("wifi"));
    fireEvent.click(acceptControl(ALERT_A));
    await waitFor(() =>
      expect(card(ALERT_A)).toHaveTextContent("הפעולה לא הושלמה. נסי שוב."),
    );
    expect(card(ALERT_A)).not.toHaveTextContent("אירעה שגיאה בלתי צפויה");
  });
});

// --- AC29: the app-level toast -----------------------------------------------

describe("AC29 — an action from the overlay confirms through the SHIPPED app-level toast", () => {
  it("produces a role=status carrying sos.acceptedCue on a section with no SosCentre", async () => {
    // On eleven of thirteen sections there is no role="status" region at all, so
    // an accept would otherwise be: the red vanishes, focus jumps to the top of
    // an unnamed <main>, and NOTHING is announced or shown.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    acceptSos.mockResolvedValue(
      alertRow({ status: "accepted", accepted_by_name: "רותם", for_me: false }),
    );

    fireEvent.click(acceptControl(ALERT_A));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("הקריאה התקבלה.");
  });

  it("announces NOTHING when the accept was TERMINAL — she does not own what she was refused", async () => {
    // ⚠ `mutate` returns `null` on a SUCCESS **and** on a terminal 401/403 —
    // «both mean the caller has nothing left to render» — and `poll.fail`
    // classifies every 403 as terminal. A cue fired on `failure === null` tells
    // a responder she owns an emergency the server just refused her, with the
    // channel-down strip rendering beside it and the card still open and
    // unowned. `SosCentre` guards exactly this (`pendingCue` + the terminal
    // check); the overlay — the surface that exists so an emergency is not
    // silently lost — did not. Reachable through CsrfOriginMiddleware's
    // CSRF_ORIGIN_MISMATCH on the mutating verb.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    acceptSos.mockRejectedValue(new ApiError(403, "FORBIDDEN", "nope"));

    fireEvent.click(acceptControl(ALERT_A));
    await screen.findByText("ערוץ הקריאות אינו פעיל.");
    await settle();

    const announced = screen
      .queryAllByRole("status")
      .map((node) => node.textContent ?? "")
      .join(" | ");
    expect(announced).not.toContain("הקריאה התקבלה.");
    // The alert really is still open and unowned — the screen must not
    // contradict itself.
    expect(cards()).toHaveLength(1);
  });

  it("says «הוסתרה» and not «נסגרה» after a dismiss, because the alert is untouched on the server", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("ההתראה הוסתרה.");
  });
});

// --- AC17: Esc, all four cases ------------------------------------------------

describe("AC17 — Esc, and the keyboard route IN that MOVE A alone does not provide", () => {
  it("from OUTSIDE moves focus into «אני מגיעה» and leaves the source input's value alone", async () => {
    // An alert announced perfectly to a user who cannot reach the ack control is
    // not an accessible alert. Shift+Tab from mid-form runs past the whole
    // ConsoleShell chrome; forward Tab is worse.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const field = screen.getByLabelText("טלפון") as HTMLInputElement;
    field.focus();
    fireEvent.change(field, { target: { value: "0501234567" } });

    fireEvent.keyDown(field, { key: "Escape" });

    // ⚠ Esc-from-outside is a DELIBERATE keypress, not an involuntary arrival,
    // which is the whole of DC-1's distinction: it lands on the control.
    // The route-in is a passive effect the keyDown does not flush, so this waits
    // for the move rather than racing it — bare, it lost that race under the
    // concurrent gate. Same fix as the sibling test below.
    await waitFor(() => expect(document.activeElement).toBe(acceptControl(ALERT_A)));
    expect(field.value).toBe("0501234567");
  });

  it("from INSIDE dismisses — so a second Esc after the route-in hides the card", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const field = screen.getByLabelText("טלפון");
    field.focus();

    fireEvent.keyDown(field, { key: "Escape" });
    const accept = acceptControl(ALERT_A);
    // ⚠ The route-in lands in a passive effect, so it is not flushed by the
    // keyDown itself. Bare, this assertion races the effect and fails under
    // parallel load.
    await waitFor(() => expect(document.activeElement).toBe(accept));

    fireEvent.keyDown(accept, { key: "Escape" });
    await waitFor(() => expect(cards()).toHaveLength(0));
  });

  it("does NOT run while a Modal is open — F36's three shipped dialogs keep their own Esc", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount(
      <Modal open onClose={() => {}} title="העברה לעמיתה">
        גוף
      </Modal>,
    );
    await screen.findByText("דנה כהן");
    const field = screen.getByLabelText("טלפון");
    field.focus();

    fireEvent.keyDown(field, { key: "Escape" });

    // The capture handler stood down; the dialog's own onCancel owns this Esc.
    expect(document.activeElement).toBe(field);
    expect(cards()).toHaveLength(1);
  });

  it("does NOT run when the event target is a <select> — a native dropdown owns its own Esc", async () => {
    // ⚠ RoomsPanel renders a bare Select on the free tile, OUTSIDE any dialog.
    // jsdom cannot reproduce the browser's dropdown, so the assertion is that
    // the handler DID NOT RUN, which it can.
    getSos.mockResolvedValue(page([alertRow()]));
    mount(
      <select aria-label="לקוחה">
        <option>מיכל</option>
      </select>,
    );
    await screen.findByText("דנה כהן");
    const picker = screen.getByLabelText("לקוחה");
    picker.focus();

    fireEvent.keyDown(picker, { key: "Escape" });

    expect(document.activeElement).toBe(picker);
    expect(cards()).toHaveLength(1);
  });
});

// --- AC28: a dismissal is never permanent ------------------------------------

describe("AC28 — a dismissal is never permanent", () => {
  it("(a) re-rises a dismissed card exactly once when it escalates", async () => {
    // A role-targeted page is for_me for an elevated caller from t=0, so a shift
    // manager can dismiss at t=2s — and with a bare id the card would still be
    // hidden when `escalated` flips at t=30s and would NEVER re-rise, defeating
    // the safety net for the exact audience escalation targets.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );
    await waitFor(() => expect(cards()).toHaveLength(0));

    getSos.mockResolvedValue(page([alertRow({ escalated: true })]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(card(ALERT_A)).toHaveTextContent("ללא מענה");

    // …and exactly once: a second dismiss silences it again.
    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );
    await waitFor(() => expect(cards()).toHaveLength(0));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(cards()).toHaveLength(0);
  });

  it("(b) renders the persistent «קריאות עזרה · N» affordance instead of null, and re-opens on it", async () => {
    // SosCentre is a child of FloorPanel, mounted on 2 of 13 sections. On the
    // other eleven the dismiss set is the ONLY state, so without this a
    // dismissal is total and permanent for a live emergency.
    getSos.mockResolvedValue(
      page([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "נועה לוי",
        }),
      ]),
    );
    mount();
    await screen.findByText("נועה לוי");
    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );
    fireEvent.click(
      within(card(ALERT_B)).getByRole("button", { name: /הסתרה/ }),
    );
    await waitFor(() => expect(cards()).toHaveLength(0));

    const reopen = screen.getByRole("button", { name: /קריאות עזרה/ });
    expect(reopen).toHaveTextContent("קריאות עזרה · 2");

    fireEvent.click(reopen);
    await waitFor(() => expect(cards()).toHaveLength(2));
  });

  it("drops the affordance once the dismissed alert stops being live", async () => {
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /קריאות עזרה/ }),
      ).toBeInTheDocument(),
    );

    getSos.mockResolvedValue(page([]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /קריאות עזרה/ })).toBeNull(),
    );
  });
});

// --- the bottom container is not a tap-swallowing band -----------------------

describe("the bottom container swallows nothing", () => {
  it("is pointer-events-none, with the two controls inside it opted back in", async () => {
    // ⚠ MEASURED IN CHROMIUM, NOT REASONED ABOUT: with the affordance alone
    // rendered, `fixed inset-x-0 bottom-0 … p-4` is an INVISIBLE full-viewport
    // band 76px tall (p-4 + the Button's min-h-11) at z-40, on all thirteen
    // sections, for as long as any dismissed alert stays live. A real click at
    // the centre of a console button in the bottom 76px reached the band and
    // never the button. `packages/ui/src/components/Toast.tsx:40` is the shipped
    // shape for exactly this and it is `pointer-events-none fixed …`.
    //
    // jsdom does no hit testing, so this pins the class contract Chromium's hit
    // testing follows; `e2e/sos.spec.ts` measures the real click.
    getSos.mockResolvedValue(page([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    fireEvent.click(
      within(card(ALERT_A)).getByRole("button", { name: /הסתרה/ }),
    );

    const reopen = await screen.findByRole("button", {
      name: /קריאות עזרה/,
    });
    const band = reopen.parentElement as HTMLElement;
    expect(band.className).toContain("fixed");
    expect(band).toHaveClass("pointer-events-none");
    expect(reopen).toHaveClass("pointer-events-auto");
  });

  it("opts the channel-down strip back in too", async () => {
    getSos.mockRejectedValue(new ApiError(403, "FORBIDDEN", "nope"));
    mount();
    const strip = await screen.findByText("ערוץ הקריאות אינו פעיל.");
    const box = strip.parentElement as HTMLElement;
    expect(box).toHaveClass("pointer-events-auto");
    expect(box.parentElement).toHaveClass("pointer-events-none");
  });
});

// --- AC27: the receiving end never dies silently -----------------------------

describe("AC27 — the channel never dies silently", () => {
  it("renders the persistent strip on a 403 and does NOT end the session", async () => {
    const ended = vi.fn();
    getSos.mockRejectedValue(new ApiError(403, "FORBIDDEN", "nope"));
    render(
      <ToastProvider>
        <SosProvider onSessionEnded={ended}>
          <SosOverlay />
          <main id="console-main" tabIndex={-1} />
        </SosProvider>
      </ToastProvider>,
    );
    await screen.findByText("ערוץ הקריאות אינו פעיל.");

    expect(
      screen.getByRole("button", { name: "רענון הדף" }),
    ).toBeInTheDocument();
    expect(ended).not.toHaveBeenCalled();
  });

  it("renders the same strip once the loop has backed off past one tick", async () => {
    getSos.mockRejectedValue(new Error("backend down"));
    mount();
    await settle();
    expect(screen.queryByText("ערוץ הקריאות אינו פעיל.")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    // «Nothing renders» is not an acceptable state for an emergency receiver
    // that has stopped receiving.
    await screen.findByText("ערוץ הקריאות אינו פעיל.");
  });

  it("renders NEITHER on a 401 — the console is dropping to the login form", async () => {
    const ended = vi.fn();
    getSos.mockRejectedValue(new ApiError(401, "UNAUTHENTICATED", "gone"));
    render(
      <ToastProvider>
        <SosProvider onSessionEnded={ended}>
          <SosOverlay />
          <main id="console-main" tabIndex={-1} />
        </SosProvider>
      </ToastProvider>,
    );
    await waitFor(() => expect(ended).toHaveBeenCalledTimes(1));

    // A strip saying the channel is down over a login screen would be true and
    // useless.
    expect(screen.queryByText("ערוץ הקריאות אינו פעיל.")).toBeNull();
    expect(cards()).toHaveLength(0);
  });
});

// --- axe, explicitly not sufficient ------------------------------------------

describe("axe", () => {
  it("passes with zero violations over the field, two cards and the bottom container", async () => {
    // ⚠ EXPLICITLY NOT SUFFICIENT, in BOTH directions. axe cannot see a focus
    // move that never happened, nor one that should not have happened; it has no
    // rule for SC 2.2.2; and it cannot see a focus ring drawn at outline-offset-2
    // on a parent's red background, which is the whole of §2.1.
    getSos.mockResolvedValue(
      page([
        alertRow({ escalated: true }),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: null,
          room_label: null,
          note: null,
        }),
      ]),
    );
    const { container } = mount();
    await screen.findByText("ללא מענה");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
