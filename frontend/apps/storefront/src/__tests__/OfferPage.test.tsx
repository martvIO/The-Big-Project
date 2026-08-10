import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BookingCreateResponse, BoutiqueResponse, WaitlistOfferView } from "../api";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { OfferPage } from "../routes/OfferPage";
import { handOff } from "../router";
import { DATE, TIME, WEEKDAY } from "../components/booking/BookingFacts";
import { expectFocus } from "../test/focus";
import { PRIVACY_FIXTURE } from "../test/boutique";

// Spread the real module so ApiError keeps its real implementation — this page
// branches on CODE and STATUS to choose between four different screens, and a
// stubbed error class would make every one of those assertions vacuous.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      lookupOffer: vi.fn(),
      claimOffer: vi.fn(),
      declineOffer: vi.fn(),
      getTerms: vi.fn(),
    },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");

// A property spy rather than vi.mock("../router"), for BookPage.test.tsx's
// recorded reason: router.tsx and OfferPage.tsx are an import CYCLE, so a mock
// factory's own importActual resolves the page's `handOff` binding back to the
// REAL module and the redirect assertion silently sees zero calls.
const handOffSpy = vi.spyOn(handOff, "leave").mockImplementation(() => undefined);
const lookupOffer = vi.mocked(api.lookupOffer);
const claimOffer = vi.mocked(api.claimOffer);
const declineOffer = vi.mocked(api.declineOffer);
const getTerms = vi.mocked(api.getTerms);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const TOKEN = "ot-abc123";
// A FIXED instant, not one built off Date.now(): the deadline line's
// today/not-today branch is real Jerusalem calendar arithmetic, and a relative
// fixture would flip the branch depending on the hour CI happened to run.
const SLOT = "2099-08-20T11:30:00Z";
const DEADLINE = "2099-08-20T09:15:00Z";

const TERMS = {
  version: 3,
  terms_text: "ביטול עד 48 שעות לפני המועד מזכה בהחזר מלא.",
  refundable_until_hours_before: 48,
  forfeit_percent: 50,
};

function offer(patch: Partial<WaitlistOfferView> = {}): WaitlistOfferView {
  return {
    status: "offered",
    starts_at: SLOT,
    expires_at: DEADLINE,
    appointment_type_name: "מדידה ראשונה",
    ...patch,
  };
}

function booking(patch: Partial<BookingCreateResponse> = {}): BookingCreateResponse {
  return {
    id: "bk-1",
    starts_at: SLOT,
    status: "confirmed",
    appointment_type_name: "מדידה ראשונה",
    dress_name: null,
    dress_size: null,
    deposit_due: false,
    redirect_url: null,
    payment_session_id: null,
    ...patch,
  };
}

function boutique(patch: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: "052-1234567",
    address: "דיזנגוף 100, תל אביב",
    maps_url: null,
    instagram: null,
    hours: [],
    exceptions: [],
    ...PRIVACY_FIXTURE,
    ...patch,
  };
}

function renderPage() {
  return render(
    <StorefrontLayout>
      <OfferPage token={TOKEN} />
    </StorefrontLayout>,
  );
}

function t(key: string): string {
  return i18n.t(key);
}

/**
 * The VISIBLE occurrence of a string.
 *
 * `offer.claimed`, `offer.declined` and `offer.gone` are each rendered twice by
 * design — once on the page and once inside the visually-hidden status region
 * that announces the outcome — so a bare getByText matches both. Filtering by
 * `.sr-only` ancestry keeps these assertions about what she SEES, with the
 * announcement asserted separately through role="status".
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

// The live offer, fully loaded, with both gates satisfied. Every claim test
// starts from here so a gate failure cannot masquerade as a claim failure.
async function arriveAtLiveOffer() {
  renderPage();
  await screen.findByLabelText(t("booking.name"));
}

function fillTheForm() {
  fireEvent.change(screen.getByLabelText(t("booking.name")), { target: { value: "נועה" } });
  fireEvent.click(screen.getByRole("checkbox", { name: t("booking.acceptTerms") }));
}

function claimButton(): HTMLElement {
  return screen.getByRole("button", { name: t("booking.submit") });
}

beforeEach(() => {
  window.history.replaceState(null, "", `/w/${TOKEN}`);
  loadBoutique.mockResolvedValue(boutique());
  lookupOffer.mockResolvedValue(offer());
  getTerms.mockResolvedValue(TERMS);
  claimOffer.mockResolvedValue(booking());
  declineOffer.mockResolvedValue(offer({ status: "cancelled" }));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("state L — loading", () => {
  it("announces the load through a hidden status region", async () => {
    // R30. A skeleton is invisible to a screen reader, so the wait has to be
    // spoken or the page is silent for as long as the network takes.
    let resolveLookup: (value: WaitlistOfferView) => void = () => undefined;
    lookupOffer.mockReturnValue(
      new Promise<WaitlistOfferView>((resolve) => {
        resolveLookup = resolve;
      }),
    );
    renderPage();

    const statuses = screen.getAllByRole("status").map((node) => node.textContent);
    expect(statuses).toContain(t("offer.loading"));

    resolveLookup(offer());
    await screen.findByLabelText(t("booking.name"));
  });
});

describe("state A — the live offer", () => {
  it("renders the slot's facts under the REUSED booking labels", async () => {
    await arriveAtLiveOffer();

    // One label, one Hebrew, no drift (design P2): the offer page must not mint
    // a second word for "when" that /book and /b/{token} do not use.
    expect(visible(t("booking.confirmWhen"))).toBeInTheDocument();
    expect(visible(t("booking.confirmWhat"))).toBeInTheDocument();
    expect(visible("מדידה ראשונה")).toBeInTheDocument();
    expect(screen.getByText(TIME.format(new Date(SLOT)))).toBeInTheDocument();
  });

  it("states the deadline ONCE, absolutely, as the hour it is", async () => {
    await arriveAtLiveOffer();

    // The lead and the time are separate children of one <p> (that IS the R19
    // shape), so the assertion reads the line rather than a single text node.
    const time = screen.getByText(TIME.format(new Date(DEADLINE)));
    expect(time.tagName).toBe("BDI");
    expect(time).toHaveAttribute("dir", "ltr");
    expect(time.parentElement).toHaveTextContent(t("offer.deadlineLead"));
  });

  it("carries the bare hour when the deadline falls TODAY", async () => {
    // The shipped case. At the two-hour default a deadline cannot cross
    // midnight (the cascade never issues after 20:59), so the line is one hour
    // and nothing else. Built off the real clock deliberately: "today" is a
    // relative rule, and a fixed fixture would test the other branch forever.
    const todayDeadline = new Date();
    lookupOffer.mockResolvedValue(offer({ expires_at: todayDeadline.toISOString() }));
    await arriveAtLiveOffer();

    const line = screen.getByText(TIME.format(todayDeadline)).parentElement;
    expect(line?.textContent).not.toContain(WEEKDAY.format(todayDeadline));
    expect(line?.textContent).not.toContain(DATE.format(todayDeadline));
  });

  it("names the deadline's weekday and date when it is NOT today", async () => {
    // The F-O1 guard itself: raise waitlist_offer_window_seconds past ~3h and a
    // 20:30 offer expires TOMORROW. A bare HH:MM would then read as today, and
    // she would arrive to a slot that went back into the pool overnight.
    await arriveAtLiveOffer();

    const deadline = new Date(DEADLINE);
    const line = screen.getByText(TIME.format(deadline)).parentElement;
    expect(line?.textContent).toContain(WEEKDAY.format(deadline));
    expect(line?.textContent).toContain(DATE.format(deadline));
  });

  it("renders the shipped legal block, not a second copy of it", async () => {
    await arriveAtLiveOffer();

    expect(screen.getByText(TERMS.terms_text)).toBeInTheDocument();
    expect(screen.getByText("48")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  // ⚠ THE R1 REGRESSION GUARD. The spec asked for a countdown; the design deck
  // removed it, and this page's SC 2.2.1 audit answer is the sentence "nothing
  // on the page auto-updates". A timer added later would still render the right
  // copy on the first paint and pass every other test in this file.
  it("does not change ANYTHING on its own — no timer, no poll, no re-render", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderPage();
      await screen.findByLabelText(t("booking.name"));
      const before = document.body.innerHTML;

      await vi.advanceTimersByTimeAsync(120_000);

      expect(document.body.innerHTML).toBe(before);
      // One lookup on mount, and not one more. A poll would satisfy the HTML
      // comparison above whenever the answer happened not to change.
      expect(lookupOffer).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("the two gates", () => {
  it("refuses an empty name and never reaches the API", async () => {
    await arriveAtLiveOffer();
    fireEvent.click(screen.getByRole("checkbox", { name: t("booking.acceptTerms") }));

    fireEvent.click(claimButton());

    expect(await screen.findByText(t("booking.nameRequired"))).toBeInTheDocument();
    expect(claimOffer).not.toHaveBeenCalled();
  });

  it("refuses an unticked policy and never reaches the API", async () => {
    await arriveAtLiveOffer();
    fireEvent.change(screen.getByLabelText(t("booking.name")), { target: { value: "נועה" } });

    fireEvent.click(claimButton());

    expect(await screen.findByText(t("booking.acceptRequired"))).toBeInTheDocument();
    expect(claimOffer).not.toHaveBeenCalled();
  });

  it("refuses a name that is only whitespace", async () => {
    await arriveAtLiveOffer();
    fireEvent.change(screen.getByLabelText(t("booking.name")), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("checkbox", { name: t("booking.acceptTerms") }));

    fireEvent.click(claimButton());

    expect(await screen.findByText(t("booking.nameRequired"))).toBeInTheDocument();
    expect(claimOffer).not.toHaveBeenCalled();
  });
});

describe("the claim", () => {
  it("posts EXACTLY three keys and no fourth", async () => {
    // Set equality, not a subset check. The entry already carries the proven
    // phone and possession of the token IS the proof, so a phone, a consent
    // flag or a verification token appearing here would be a new collection
    // point on a surface whose privacy notice does not declare one.
    await arriveAtLiveOffer();
    fillTheForm();

    fireEvent.click(claimButton());

    await waitFor(() => {
      expect(claimOffer).toHaveBeenCalledTimes(1);
    });
    const body = claimOffer.mock.calls[0][0];
    expect(Object.keys(body).sort()).toEqual(["name", "terms_version", "token"]);
    expect(body).toEqual({ token: TOKEN, name: "נועה", terms_version: TERMS.version });
  });
});

describe("state C — claimed with no deposit", () => {
  it("keeps the facts, replaces both buttons and focuses the outcome", async () => {
    await arriveAtLiveOffer();
    fillTheForm();
    fireEvent.click(claimButton());

    const line = await findVisible(t("offer.claimed"));
    await expectFocus(line);
    expect(line).toHaveAttribute("tabindex", "-1");
    // The facts survive the transition: she is owed the time she just booked.
    expect(visible(t("booking.confirmWhen"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("booking.submit") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("offer.declineCta") })).toBeNull();
    expect(handOffSpy).not.toHaveBeenCalled();
  });
});

describe("state B — claimed on a deposit type", () => {
  it("renders F19's SHIPPED hand-off and leaves for the hosted page", async () => {
    // Zero new payment code and zero new copy (spec D5): the deposit branch is
    // the booking flow's, verbatim. /w/{token} is not a second checkout.
    claimOffer.mockResolvedValue(
      booking({
        status: "pending_payment",
        deposit_due: true,
        redirect_url: "https://pay.example.test/s/xyz",
      }),
    );
    await arriveAtLiveOffer();
    fillTheForm();
    fireEvent.click(claimButton());

    expect(await findVisible(t("booking.payHandoff"))).toBeInTheDocument();
    expect(visible(t("booking.payManualHint"))).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: t("booking.payManualCta") }),
    ).toHaveAttribute("href", "https://pay.example.test/s/xyz");
    await waitFor(() => {
      expect(handOffSpy).toHaveBeenCalledWith("https://pay.example.test/s/xyz");
    });
  });
});

describe("state D — already claimed", () => {
  it("makes no delivery claim about the manage link", async () => {
    // Design P3. The provider can be unconfigured, so "the link was sent to
    // you" is a promise the product cannot keep; the phone always works.
    lookupOffer.mockResolvedValue(offer({ status: "claimed" }));
    renderPage();

    expect(await findVisible(t("offer.claimedReturning"))).toBeInTheDocument();
    expect(visible(t("manage.invalidHint"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("booking.submit") })).toBeNull();
  });
});

describe("state E — expired", () => {
  it("states the fact and offers the shipped rebook path", async () => {
    lookupOffer.mockResolvedValue(offer({ status: "expired" }));
    renderPage();

    expect(await findVisible(t("offer.expired"))).toBeInTheDocument();
    expect(visible(t("offer.pickAnotherHint"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t("manage.rebookCta") })).toHaveAttribute(
      "href",
      "/book/slot",
    );
    // No form on a dead offer: a tick and a name field she could fill in would
    // be a button that can only fail.
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});

describe("state F — the seat went to someone else", () => {
  it("shows the same sentence a direct booker meets, and STAYS on the live offer", async () => {
    // ⚠ F-O2, and it is deliberate. The claim's transaction rolled back, so the
    // entry is still `offered` — the form remains, and a reload re-renders the
    // LIVE offer until the deadline passes. Do NOT "fix" this by expiring the
    // entry client-side; the server is the only clock.
    claimOffer.mockRejectedValue(new ApiError(409, "SLOT_UNAVAILABLE", "gone"));
    await arriveAtLiveOffer();
    fillTheForm();
    fireEvent.click(claimButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(t("offer.gone"));
    await expectFocus(alert);
    expect(claimButton()).toBeInTheDocument();
    expect(screen.getByText(TERMS.terms_text)).toBeInTheDocument();
  });
});

describe("state J — the policy was republished mid-read", () => {
  it("clears the tick and re-reads the CURRENT policy", async () => {
    // A box ticked against a superseded policy is not consent.
    claimOffer.mockRejectedValue(new ApiError(409, "TERMS_STALE", "stale"));
    await arriveAtLiveOffer();
    fillTheForm();
    expect(screen.getByRole("checkbox", { name: t("booking.acceptTerms") })).toBeChecked();

    fireEvent.click(claimButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(t("errors.termsStale"));
    await waitFor(() => {
      expect(screen.getByRole("checkbox", { name: t("booking.acceptTerms") })).not.toBeChecked();
    });
    // The re-read is what makes the cleared tick meaningful — otherwise she
    // would be re-ticking the same superseded text.
    await waitFor(() => {
      expect(lookupOffer).toHaveBeenCalledTimes(2);
    });
  });
});

describe("the decline", () => {
  it("takes TWO steps, and the first one calls nothing", async () => {
    // Declining writes `cancelled` — it takes her off the day's list entirely,
    // not past one slot (design P2). One tap must never do that.
    await arriveAtLiveOffer();

    fireEvent.click(screen.getByRole("button", { name: t("offer.declineCta") }));

    expect(declineOffer).not.toHaveBeenCalled();
    const question = await findVisible(t("offer.declineQuestion"));
    await expectFocus(question);
    expect(visible(t("offer.declineConsequence"))).toBeInTheDocument();
  });

  it("backs out and returns focus to the re-mounted trigger", async () => {
    await arriveAtLiveOffer();
    fireEvent.click(screen.getByRole("button", { name: t("offer.declineCta") }));
    await findVisible(t("offer.declineQuestion"));

    fireEvent.click(screen.getByRole("button", { name: t("manage.cancelKeep") }));

    // The mover is the state change that mounted the target — the trigger is a
    // freshly mounted node, so a synchronous .focus() on the old one would drop
    // focus to <body>.
    await expectFocus(screen.getByRole("button", { name: t("offer.declineCta") }));
    expect(declineOffer).not.toHaveBeenCalled();
  });

  it("confirms into the declined state and says what it cost her", async () => {
    await arriveAtLiveOffer();
    fireEvent.click(screen.getByRole("button", { name: t("offer.declineCta") }));
    await findVisible(t("offer.declineQuestion"));

    fireEvent.click(screen.getByRole("button", { name: t("offer.declineConfirm") }));

    await waitFor(() => {
      expect(declineOffer).toHaveBeenCalledWith(TOKEN);
    });
    const line = await findVisible(t("offer.declined"));
    await expectFocus(line);
    expect(visible(t("offer.pickAnotherHint"))).toBeInTheDocument();
  });
});

describe("state G — a lookup on an already-declined entry", () => {
  it("renders the declined copy rather than a live form", async () => {
    lookupOffer.mockResolvedValue(offer({ status: "cancelled" }));
    renderPage();

    expect(await findVisible(t("offer.declined"))).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});

describe("state H — unknown, dead, or another boutique's token", () => {
  it("is ONE indistinguishable state, with no oracle", async () => {
    // The manage page's rule verbatim. A token that 404s because it belongs to
    // a different tenant must be unanswerable from one that never existed.
    lookupOffer.mockRejectedValue(new ApiError(404, "NOT_FOUND", "no"));
    renderPage();

    expect(await findVisible(t("manage.invalid"))).toBeInTheDocument();
    expect(visible(t("manage.invalidHint"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("manage.retry") })).toBeNull();
  });
});

describe("state I — the load failed", () => {
  it("offers a retry that actually re-issues the lookup", async () => {
    lookupOffer.mockRejectedValueOnce(new ApiError(500, "INTERNAL", "boom"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(t("manage.loadFailed"));
    fireEvent.click(screen.getByRole("button", { name: t("manage.retry") }));

    await screen.findByLabelText(t("booking.name"));
    expect(lookupOffer).toHaveBeenCalledTimes(2);
  });

  it("treats a throttled lookup as a load failure, not as a dead link", async () => {
    // 429 is "ask again", 404 is "never ask again". Collapsing them would tell a
    // bride her live offer is gone because she refreshed twice.
    lookupOffer.mockRejectedValue(new ApiError(429, "TOO_MANY_ATTEMPTS", "slow down"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(t("manage.loadFailed"));
    expect(screen.queryByText(t("manage.invalid"))).toBeNull();
  });
});
