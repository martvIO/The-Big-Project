import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BoutiqueResponse, ManageBookingResponse } from "../api";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { ManageBookingPage } from "../routes/ManageBookingPage";
import { expectFocus } from "../test/focus";
import { inPaintGap } from "../test/interleave";

// Spread the real module so ApiError keeps its real implementation — the page
// branches on error CODE and STATUS, and a stubbed error class would make every
// state assertion below vacuous.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      lookupBooking: vi.fn(),
      confirmAttendance: vi.fn(),
      cancelBooking: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const lookup = vi.mocked(api.lookupBooking);
const confirmAttendance = vi.mocked(api.confirmAttendance);
const cancelBooking = vi.mocked(api.cancelBooking);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const TOKEN = "mt-abc123";
// Fixed instants rather than relative ones: the past/upcoming split is real
// clock arithmetic in the page, and a fixture built from Date.now() would drift.
const UPCOMING = "2099-08-04T07:00:00Z";
const ALREADY_PASSED = "2000-08-04T07:00:00Z";

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

function answer(overrides: {
  booking?: Partial<ManageBookingResponse["booking"]>;
  policy?: ManageBookingResponse["policy"];
  boutique?: Partial<ManageBookingResponse["boutique"]>;
}): ManageBookingResponse {
  return {
    booking: {
      starts_at: UPCOMING,
      status: "confirmed",
      attendance_confirmed_at: null,
      appointment_type_name: "מדידה ראשונה",
      dress_name: null,
      dress_size: null,
      ...overrides.booking,
    },
    policy:
      overrides.policy === undefined
        ? { refundable_until_hours_before: 48, forfeit_percent: 50 }
        : overrides.policy,
    boutique: {
      name: "בוטיק אלמה",
      phone: "052-1234567",
      address: "דיזנגוף 100, תל אביב",
      maps_url: null,
      ...overrides.boutique,
    },
  };
}

function renderPage() {
  return render(
    <StorefrontLayout>
      <ManageBookingPage token={TOKEN} />
    </StorefrontLayout>,
  );
}

function t(key: string): string {
  return i18n.t(key);
}

/**
 * The VISIBLE occurrence of a string.
 *
 * `manage.attendanceDone` and `manage.cancelled` are each rendered twice by
 * design — once on the page and once inside the visually-hidden status region
 * that announces the outcome — so a bare getByText matches both. Filtering by
 * `.sr-only` ancestry is what keeps these assertions about what she SEES, with
 * the announcement asserted separately through role="status".
 */
function visible(value: string): HTMLElement {
  const matches = screen.getAllByText(value).filter((node) => node.closest(".sr-only") === null);
  if (matches.length !== 1) {
    throw new Error(`expected exactly one visible ${value}, found ${matches.length}`);
  }
  return matches[0];
}

async function findVisible(value: string): Promise<HTMLElement> {
  await waitFor(() => {
    expect(
      screen.getAllByText(value).filter((node) => node.closest(".sr-only") === null),
    ).toHaveLength(1);
  });
  return visible(value);
}

beforeEach(() => {
  window.history.replaceState(null, "", `/b/${TOKEN}`);
  loadBoutique.mockResolvedValue(boutique());
  lookup.mockResolvedValue(answer({}));
  confirmAttendance.mockResolvedValue(
    answer({ booking: { attendance_confirmed_at: "2099-08-03T07:00:00Z" } }),
  );
  cancelBooking.mockResolvedValue(answer({ booking: { status: "cancelled" } }));
});

afterEach(() => {
  vi.clearAllMocks();
});

// --- state S: skeleton ------------------------------------------------------

describe("state S — loading", () => {
  it("announces the load in a status region rather than with aria-busy alone", async () => {
    // R30: aria-busy on a plain div is announced by neither VoiceOver nor NVDA,
    // so the loading state carries a real status region.
    lookup.mockReturnValue(new Promise(() => undefined));
    renderPage();

    expect(screen.getByTestId("manage-loading")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(t("manage.loading"));
    // The heading is present from the first paint, so the page is never untitled.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(t("manage.title"));
  });

  it("passes the token from the route to the lookup", async () => {
    renderPage();
    await waitFor(() => {
      expect(lookup).toHaveBeenCalledWith(TOKEN);
    });
  });
});

// --- state L: loaded, upcoming ---------------------------------------------

describe("state L — loaded and upcoming", () => {
  it("renders the facts and both actions", async () => {
    lookup.mockResolvedValue(
      answer({ booking: { dress_name: "שמלת אלמה", dress_size: "36" } }),
    );
    renderPage();

    expect(await screen.findByText(t("booking.confirmWhen"))).toBeInTheDocument();
    expect(screen.getByText("מדידה ראשונה")).toBeInTheDocument();
    expect(screen.getByText("שמלת אלמה")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("manage.attendanceCta") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("manage.cancelCta") })).toBeInTheDocument();
  });

  it("renders the appointment in the boutique's zone, not the device's", async () => {
    // 07:00Z is 10:00 in Jerusalem. The suite runs in another zone, so a naive
    // toLocaleString would print a different hour here — which is the bug.
    renderPage();
    const when = await screen.findByText(/10:00/);
    expect(when).toBeInTheDocument();
  });

  it("isolates every numeral island so an RTL line cannot reorder it", async () => {
    // R19: dates, times and the policy hours are LTR runs inside a Hebrew line.
    renderPage();
    await screen.findByText(t("booking.confirmWhen"));
    const isolated = [...document.querySelectorAll("bdi[dir='ltr']")].map((n) => n.textContent);
    expect(isolated.some((text) => text?.includes("10:00"))).toBe(true);
    expect(isolated).toContain("48");
  });

  it("shows the accepted policy window before the cancel step is even opened", async () => {
    renderPage();
    expect(await screen.findByText(t("manage.cancelPolicyLead"), { exact: false })).toBeVisible();
  });

  it("prefers the layout fetch over the payload for the contact block", async () => {
    // F-M2: useBoutique() is PRIMARY. It carries the full profile (Instagram
    // included, which the manage payload deliberately omits), so the payload
    // must not win when both are present.
    loadBoutique.mockResolvedValue(boutique({ phone: "050-1111111" }));
    lookup.mockResolvedValue(answer({ boutique: { phone: "059-9999999" } }));
    renderPage();

    await waitFor(() => {
      expect(document.querySelector('a[href="tel:050-1111111"]')).not.toBeNull();
    });
    expect(document.querySelector('a[href="tel:059-9999999"]')).toBeNull();
  });

  it("falls back to the payload's boutique block when the layout fetch failed", async () => {
    // F-M2 as corrected at the gate: the payload is a fallback, and it exists
    // only inside a 200 — so it can serve L/L2/C/P and nothing else.
    loadBoutique.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    lookup.mockResolvedValue(answer({ boutique: { phone: "053-7654321" } }));
    renderPage();

    await screen.findByText(t("booking.confirmWhen"));
    await waitFor(() => {
      expect(document.querySelector('a[href="tel:053-7654321"]')).not.toBeNull();
    });
  });
});

// --- state L2: attendance confirmed ---------------------------------------

describe("state L2 — attendance confirmed", () => {
  it("replaces the primary button with the success line and announces it", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.attendanceCta") }));

    expect(await findVisible(t("manage.attendanceDone"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("manage.attendanceCta") })).toBeNull();
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(t("manage.attendanceDone"));
    });
  });

  it("moves focus to the line it just mounted, never to the body", async () => {
    // The control that was clicked is gone, so this transition rules its own
    // focus destination — otherwise focus drops to <body> after the one action
    // the page exists for.
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.attendanceCta") }));

    const done = await findVisible(t("manage.attendanceDone"));
    await expectFocus(done);
  });

  it("keeps cancel available after attendance is confirmed", async () => {
    // Design P3: confirming attendance is a courtesy signal, not a lock-in.
    lookup.mockResolvedValue(
      answer({ booking: { attendance_confirmed_at: "2099-08-03T07:00:00Z" } }),
    );
    renderPage();

    expect(await screen.findByText(t("manage.attendanceDone"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("manage.cancelCta") })).toBeInTheDocument();
  });

  it("renders the confirmed state straight from a lookup, not only after a tap", async () => {
    // She will re-open the link. The second visit must show the same outcome.
    lookup.mockResolvedValue(
      answer({ booking: { attendance_confirmed_at: "2099-08-03T07:00:00Z" } }),
    );
    renderPage();
    expect(await screen.findByText(t("manage.attendanceDone"))).toBeInTheDocument();
    expect(confirmAttendance).not.toHaveBeenCalled();
  });

  it("uses no exclamation mark anywhere on the page", async () => {
    // pre-decided #5, and mechanically checkable: the whole storefront bundle
    // contains zero exclamation marks, so one here would be the single string
    // that breaks the product's punctuation register.
    lookup.mockResolvedValue(
      answer({ booking: { attendance_confirmed_at: "2099-08-03T07:00:00Z" } }),
    );
    renderPage();
    await screen.findByText(t("manage.attendanceDone"));
    expect(document.body.textContent).not.toContain("!");
  });
});

// --- the cancel two-step --------------------------------------------------

describe("the cancel two-step", () => {
  it("does not cancel on the first tap", async () => {
    // One tap must never cancel a wedding-dress appointment.
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));

    expect(cancelBooking).not.toHaveBeenCalled();
    expect(screen.getByText(t("manage.cancelQuestion"))).toBeInTheDocument();
    expect(screen.getByText(t("manage.cancelConsequenceFree"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("manage.cancelConfirm") })).toBeInTheDocument();
  });

  it("moves focus into the revealed block, onto the question itself", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));

    await expectFocus(screen.getByText(t("manage.cancelQuestion")));
  });

  // --- the pending intent must survive a render it did not ask for ---------
  //
  // The page defers each focus move to the effect below the render that mounts
  // its target, because the target does not exist when the tap decides on it.
  // The effect CLEARS the intent before it knows the focus landed, so a render
  // that commits in between discards the move for good — ?.focus() no-ops on a
  // ref that is still null, and there is no second attempt.
  //
  // A browser reaches that in-between: React runs passive effects in a task of
  // their own, after paint, and a tap on a busy device lands in the gap. Every
  // other test here stays inside act(), where the gap does not exist — which is
  // exactly why this defect ships green locally and failed CI run 30623316694
  // on the reveal test below, with focus on <body>.

  it("keeps the reveal's focus when the tap lands in the gap after a paint", async () => {
    // The layout's boutique read is held so its arrival is the paint she taps
    // through — the ordinary case, since it is in flight for every visit.
    let settle: (value: BoutiqueResponse) => void = () => undefined;
    loadBoutique.mockReturnValue(
      new Promise<BoutiqueResponse>((resolve) => {
        settle = resolve;
      }),
    );
    renderPage();
    const trigger = await screen.findByRole("button", { name: t("manage.cancelCta") });

    await inPaintGap(
      () => {
        settle(boutique());
      },
      () => {
        trigger.click();
      },
    );

    // expectFocus, not a bare read: against the FIXED code the move genuinely is
    // later — it lands on the commit that mounts the block — so a runner too
    // loaded to drain the flush inside the gap's settle would fail on timing
    // alone, which is the very failure mode this branch exists to delete.
    // Polling cannot rescue the defect being pinned: a discarded intent never
    // fires, so the unfixed code spends the whole timeout and still goes red.
    await expectFocus(screen.getByText(t("manage.cancelQuestion")));
  });

  it("keeps the collapse's focus when the tap lands in the gap after a paint", async () => {
    // Same window, the other intent: the trigger is UNMOUNTED while the reveal
    // is open, so its ref is null in any render that commits before the
    // collapse — and clearing there leaves her on a <p> that is about to go.
    let settle: (value: BoutiqueResponse) => void = () => undefined;
    loadBoutique.mockReturnValue(
      new Promise<BoutiqueResponse>((resolve) => {
        settle = resolve;
      }),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));
    const keep = screen.getByRole("button", { name: t("manage.cancelKeep") });

    await inPaintGap(
      () => {
        settle(boutique());
      },
      () => {
        keep.click();
      },
    );

    await expectFocus(screen.getByRole("button", { name: t("manage.cancelCta") }));
  });

  it("collapses on 'keep' and returns focus to the trigger", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));
    fireEvent.click(screen.getByRole("button", { name: t("manage.cancelKeep") }));

    expect(screen.queryByText(t("manage.cancelQuestion"))).toBeNull();
    expect(cancelBooking).not.toHaveBeenCalled();
    await expectFocus(screen.getByRole("button", { name: t("manage.cancelCta") }));
  });

  it("shows the window from HER accepted policy, isolated as an LTR run", async () => {
    lookup.mockResolvedValue(
      answer({ policy: { refundable_until_hours_before: 72, forfeit_percent: 25 } }),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));

    const isolated = [...document.querySelectorAll("bdi[dir='ltr']")].map((n) => n.textContent);
    expect(isolated).toContain("72");
    expect(isolated).not.toContain("48");
  });

  it("renders the same free-cancellation sentence on both sides of the window", async () => {
    // Design P1 / pre-decided #4: every F16-era booking is deposit-free, so a
    // forfeit warning about a deposit that was never taken would be a lie. The
    // window fact is shown; the consequence does not change with it.
    lookup.mockResolvedValue(
      answer({ policy: { refundable_until_hours_before: 100_000, forfeit_percent: 100 } }),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));

    expect(screen.getByText(t("manage.cancelConsequenceFree"))).toBeInTheDocument();
  });

  it("omits the window sentence when the accepted policy row has gone", async () => {
    lookup.mockResolvedValue(answer({ policy: null }));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));

    expect(screen.getByText(t("manage.cancelConsequenceFree"))).toBeInTheDocument();
    expect(screen.queryByText(t("manage.cancelPolicyLead"), { exact: false })).toBeNull();
  });

  it("cancels on the confirm tap and renders the cancelled state", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));
    fireEvent.click(screen.getByRole("button", { name: t("manage.cancelConfirm") }));

    expect(await findVisible(t("manage.cancelled"))).toBeInTheDocument();
    expect(cancelBooking).toHaveBeenCalledWith(TOKEN);
  });

  it("is the only place the danger variant appears", async () => {
    // Design P5: danger is reserved for the click that destroys. The reveal
    // trigger stays secondary.
    renderPage();
    await screen.findByRole("button", { name: t("manage.cancelCta") });
    expect(document.querySelectorAll(".bg-danger")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: t("manage.cancelCta") }));
    expect(document.querySelectorAll(".bg-danger")).toHaveLength(1);
  });
});

// --- state C: cancelled ---------------------------------------------------

describe("state C — cancelled", () => {
  it("keeps the facts, drops the actions and offers a rebook link", async () => {
    lookup.mockResolvedValue(answer({ booking: { status: "cancelled" } }));
    renderPage();

    expect(await screen.findByText(t("manage.cancelled"))).toBeInTheDocument();
    // The facts stay: she may need the date to rebook (design P4).
    expect(screen.getByText(t("booking.confirmWhen"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("manage.attendanceCta") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("manage.cancelCta") })).toBeNull();
    expect(screen.getByRole("link", { name: t("manage.rebookCta") })).toHaveAttribute(
      "href",
      "/book/slot",
    );
  });

  it("moves focus to the cancelled line after the cancellation", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));
    fireEvent.click(screen.getByRole("button", { name: t("manage.cancelConfirm") }));

    const line = await findVisible(t("manage.cancelled"));
    await expectFocus(line);
  });
});

// --- state P: past --------------------------------------------------------

describe("state P — the appointment has passed", () => {
  it("stays readable and drops both actions", async () => {
    // The recorded amendment of checklist row 21: actions expire at starts_at,
    // the page does not. An honest "this has passed" beats a dead link.
    lookup.mockResolvedValue(answer({ booking: { starts_at: ALREADY_PASSED } }));
    renderPage();

    expect(await screen.findByText(t("manage.past"))).toBeInTheDocument();
    expect(screen.getByText(t("booking.confirmWhen"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("manage.attendanceCta") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("manage.cancelCta") })).toBeNull();
  });

  it("prefers the cancelled state over the past state for a cancelled old booking", async () => {
    lookup.mockResolvedValue(
      answer({ booking: { starts_at: ALREADY_PASSED, status: "cancelled" } }),
    );
    renderPage();

    expect(await screen.findByText(t("manage.cancelled"))).toBeInTheDocument();
    expect(screen.queryByText(t("manage.past"))).toBeNull();
  });
});

// --- state X: invalid link ------------------------------------------------

describe("state X — invalid link", () => {
  it("renders the invalid copy with no facts card", async () => {
    lookup.mockRejectedValue(new ApiError(404, "BOOKING_LINK_INVALID", "gone"));
    renderPage();

    expect(await screen.findByText(t("manage.invalid"))).toBeInTheDocument();
    expect(screen.getByText(t("manage.invalidHint"))).toBeInTheDocument();
    expect(screen.queryByText(t("booking.confirmWhen"))).toBeNull();
    expect(screen.queryByRole("button", { name: t("manage.retry") })).toBeNull();
  });

  it("never paints the server's English message onto a Hebrew page", async () => {
    lookup.mockRejectedValue(new ApiError(404, "BOOKING_LINK_INVALID", "This link is no longer valid."));
    renderPage();

    await screen.findByText(t("manage.invalid"));
    expect(screen.queryByText(/This link is no longer valid/)).toBeNull();
  });

  it("renders no contact block at all when the layout fetch also failed", async () => {
    // A lookup FAILURE's response is the house error shape and carries no
    // boutique data under any circumstance (F-M2), so there is nothing to fall
    // back to and the copy has to stand on its own.
    loadBoutique.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    lookup.mockRejectedValue(new ApiError(404, "BOOKING_LINK_INVALID", "gone"));
    renderPage();

    await screen.findByText(t("manage.invalid"));
    await waitFor(() => {
      expect(document.querySelector('a[href^="tel:"]')).toBeNull();
    });
  });

  it("does not treat a plain NOT_FOUND as an invalid link", async () => {
    // BOOKING_LINK_INVALID is its own code precisely so a rotated manage token
    // is distinguishable from an archived dress on the same origin.
    lookup.mockRejectedValue(new ApiError(404, "NOT_FOUND", "nope"));
    renderPage();

    expect(await screen.findByText(t("manage.loadFailed"))).toBeInTheDocument();
    expect(screen.queryByText(t("manage.invalid"))).toBeNull();
  });
});

// --- state R: retryable failure ------------------------------------------

describe("state R — retryable failure", () => {
  it("offers a retry and the phone on a throttle trip", async () => {
    lookup.mockRejectedValueOnce(new ApiError(429, "TOO_MANY_ATTEMPTS", "slow down"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(t("manage.loadFailed"));
    expect(screen.getByRole("button", { name: t("manage.retry") })).toBeInTheDocument();
  });

  it("recovers on retry", async () => {
    lookup.mockRejectedValueOnce(new ApiError(503, "UNKNOWN", "down"));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.retry") }));

    expect(await screen.findByText(t("booking.confirmWhen"))).toBeInTheDocument();
    expect(lookup).toHaveBeenCalledTimes(2);
  });

  it("treats a dropped connection the same as a 5xx", async () => {
    lookup.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    renderPage();
    expect(await screen.findByText(t("manage.loadFailed"))).toBeInTheDocument();
  });
});

// --- state precedence when an action races the clock ---------------------

describe("an action that loses to the clock or another device", () => {
  it("re-renders the past state from the server after a 409 ALREADY_STARTED", async () => {
    // The page always re-renders from the response, never from what the tap
    // optimistically hoped.
    renderPage();
    await screen.findByRole("button", { name: t("manage.attendanceCta") });
    confirmAttendance.mockRejectedValue(
      new ApiError(409, "BOOKING_ALREADY_STARTED", "started"),
    );
    lookup.mockResolvedValue(answer({ booking: { starts_at: ALREADY_PASSED } }));

    fireEvent.click(screen.getByRole("button", { name: t("manage.attendanceCta") }));

    expect(await screen.findByText(t("manage.past"))).toBeInTheDocument();
    expect(screen.queryByText(t("manage.attendanceDone"))).toBeNull();
  });

  it("re-renders the cancelled state after a 409 BOOKING_CANCELLED", async () => {
    renderPage();
    await screen.findByRole("button", { name: t("manage.attendanceCta") });
    confirmAttendance.mockRejectedValue(new ApiError(409, "BOOKING_CANCELLED", "cancelled"));
    lookup.mockResolvedValue(answer({ booking: { status: "cancelled" } }));

    fireEvent.click(screen.getByRole("button", { name: t("manage.attendanceCta") }));

    expect(await screen.findByText(t("manage.cancelled"))).toBeInTheDocument();
  });

  it("closes the cancel reveal when a cancel loses the race", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: t("manage.cancelCta") }));
    cancelBooking.mockRejectedValue(new ApiError(409, "BOOKING_ALREADY_STARTED", "started"));
    lookup.mockResolvedValue(answer({ booking: { starts_at: ALREADY_PASSED } }));

    fireEvent.click(screen.getByRole("button", { name: t("manage.cancelConfirm") }));

    expect(await screen.findByText(t("manage.past"))).toBeInTheDocument();
    expect(screen.queryByText(t("manage.cancelQuestion"))).toBeNull();
  });
});

// --- what the page never does -------------------------------------------

describe("what this page deliberately does not have", () => {
  it("ships no stepper and no reschedule action", async () => {
    // Not a flow (she arrived from a text), and a self-serve reschedule is a
    // bigger product decision than a comms feature should smuggle in.
    renderPage();
    await screen.findByText(t("booking.confirmWhen"));
    expect(screen.queryByLabelText(t("booking.stepsLabel"))).toBeNull();
    expect(screen.queryByRole("list", { name: t("booking.stepsLabel") })).toBeNull();
  });

  it("never puts the token into the DOM", async () => {
    // The token is body-carried on the wire; a stray render into a data
    // attribute or a link would put it back into a place that gets shared.
    renderPage();
    await screen.findByText(t("booking.confirmWhen"));
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });
});
