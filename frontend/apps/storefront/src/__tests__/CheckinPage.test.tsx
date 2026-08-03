import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BoutiqueResponse, TicketView } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { CheckinPage } from "../routes/CheckinPage";
import { expectFocus } from "../test/focus";

// Spread the real module so ApiError keeps its real implementation — the page
// branches on error CODE, and a stubbed error class would make the throttle
// assertion vacuous.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, createCheckin: vi.fn(), getQueuePosition: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const createCheckin = vi.mocked(api.createCheckin);
const getQueuePosition = vi.mocked(api.getQueuePosition);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const BOUTIQUE_NAME = "בוטיק אלמה";
const TICKET_ID = "11111111-2222-3333-4444-555555555555";

function boutique(overrides: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: BOUTIQUE_NAME,
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

function ticket(overrides: Partial<TicketView> = {}): TicketView {
  return { id: TICKET_ID, status: "waiting", position: 3, called_at: null, ...overrides };
}

function t(key: string, options?: Record<string, string>): string {
  return i18n.t(key, options);
}

function renderPage() {
  return render(
    <StorefrontLayout>
      <CheckinPage />
    </StorefrontLayout>,
  );
}

// The form only exists once the boutique block has landed — the collection
// notice may never render without the data controller's name in it.
async function renderLoadedForm() {
  const result = renderPage();
  await screen.findByLabelText(t("checkin.name"));
  return result;
}

function nameField(): HTMLInputElement {
  return screen.getByLabelText(t("checkin.name"));
}

function phoneField(): HTMLInputElement {
  return screen.getByLabelText(t("checkin.phone"));
}

function submitButton(): HTMLElement {
  return screen.getByRole("button", { name: t("checkin.submit") });
}

async function fillValid() {
  fireEvent.change(nameField(), { target: { value: "נועה" } });
  fireEvent.change(phoneField(), { target: { value: "0501234567" } });
  fireEvent.click(screen.getByLabelText(t("checkin.visitBride")));
}

beforeEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/checkin");
  loadBoutique.mockResolvedValue(boutique());
});

afterEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/");
});

// --- validation: on the forward press and nowhere else -----------------------

describe("CheckinPage validation", () => {
  it("surfaces nothing on input or on blur — only the forward press validates", async () => {
    await renderLoadedForm();

    fireEvent.change(nameField(), { target: { value: "" } });
    fireEvent.blur(nameField());
    fireEvent.change(phoneField(), { target: { value: "05" } });
    fireEvent.blur(phoneField());

    expect(screen.queryByText(t("booking.nameRequired"))).not.toBeInTheDocument();
    expect(screen.queryByText(t("booking.phoneInvalid"))).not.toBeInTheDocument();
    expect(screen.queryByText(t("checkin.visitTypeRequired"))).not.toBeInTheDocument();
  });

  it("sets every message at once on the forward press", async () => {
    await renderLoadedForm();
    fireEvent.change(phoneField(), { target: { value: "05" } });

    fireEvent.click(submitButton());

    expect(screen.getByText(t("booking.nameRequired"))).toBeInTheDocument();
    expect(screen.getByText(t("booking.phoneInvalid"))).toBeInTheDocument();
    expect(screen.getByText(t("checkin.visitTypeRequired"))).toBeInTheDocument();
  });

  it("issues NO request when validation fails", async () => {
    await renderLoadedForm();

    fireEvent.click(submitButton());

    expect(createCheckin).not.toHaveBeenCalled();
  });

  it("lands focus on the first failure, and only on the first", async () => {
    await renderLoadedForm();

    fireEvent.click(submitButton());
    await expectFocus(nameField());

    fireEvent.change(nameField(), { target: { value: "נועה" } });
    fireEvent.click(submitButton());
    await expectFocus(phoneField());

    fireEvent.change(phoneField(), { target: { value: "0501234567" } });
    fireEvent.click(submitButton());
    await expectFocus(screen.getByLabelText(t("checkin.visitBride")));
  });

  it("refuses a name the shipped helper refuses, and never invents a second rule", async () => {
    // validateName is imported as it is — no client-side constant mirrors a
    // server bound, so test_frontend_constant_parity.py gains no row.
    await renderLoadedForm();
    fireEvent.change(nameField(), { target: { value: "א".repeat(81) } });
    fireEvent.change(phoneField(), { target: { value: "0501234567" } });
    fireEvent.click(screen.getByLabelText(t("checkin.visitBride")));

    fireEvent.click(submitButton());

    expect(screen.getByText(t("booking.nameTooLong"))).toBeInTheDocument();
    expect(createCheckin).not.toHaveBeenCalled();
  });
});

// --- the request ------------------------------------------------------------

describe("CheckinPage submit", () => {
  it("sends the normalized phone and the chosen visit type", async () => {
    createCheckin.mockResolvedValue(ticket());
    await renderLoadedForm();
    fireEvent.change(nameField(), { target: { value: "נועה" } });
    fireEvent.change(phoneField(), { target: { value: "050-123-4567" } });
    fireEvent.click(screen.getByLabelText(t("checkin.visitEvening")));

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(createCheckin).toHaveBeenCalledWith({
        name: "נועה",
        phone: "+972501234567",
        visit_type: "evening",
        marketing_opt_in: false,
      });
    });
  });

  it("leaves the opt-in UNCHECKED by default", async () => {
    await renderLoadedForm();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("carries a ticked opt-in into the request", async () => {
    createCheckin.mockResolvedValue(ticket());
    await renderLoadedForm();
    await fillValid();
    fireEvent.click(screen.getByRole("checkbox"));

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(createCheckin).toHaveBeenCalledWith(
        expect.objectContaining({ marketing_opt_in: true }),
      );
    });
  });

  it("fires ONE request on a double tap", async () => {
    // Guarded by a re-entrant boolean, not by `disabled`: React commits
    // `disabled` asynchronously and a fast double-tap on iOS fires two clicks
    // inside one frame.
    let settle: (value: TicketView) => void = () => undefined;
    createCheckin.mockImplementation(
      () =>
        new Promise<TicketView>((resolve) => {
          settle = resolve;
        }),
    );
    await renderLoadedForm();
    await fillValid();

    const button = submitButton();
    fireEvent.click(button);
    fireEvent.click(button);

    expect(createCheckin).toHaveBeenCalledTimes(1);
    await act(async () => {
      settle(ticket());
    });
  });

  it("navigates to the ticket's own page on every successful create", async () => {
    createCheckin.mockResolvedValue(ticket());
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.location.pathname).toBe(`/q/${TICKET_ID}`);
    });
  });
});

// --- the throttle, and the focus move a failure owes her ---------------------

describe("CheckinPage failure paths", () => {
  it("renders its OWN throttle copy, which names no duration and offers no retry", async () => {
    createCheckin.mockRejectedValue(
      new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts. Try again later."),
    );
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(t("checkin.budgetSpent"));
    // The shared copy would say "try again in a moment"; the create budget's
    // window is an hour, and the 429 body carries no duration at all.
    expect(alert).not.toHaveTextContent(t("errors.tooManyAttempts"));
    expect(createCheckin).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/checkin");
  });

  it("moves focus to the error a failed submit produced", async () => {
    // A useEffect keyed on the failure, NEVER a .focus() in the catch: the alert
    // node does not exist yet when setState runs, so the call in the catch is a
    // no-op on nothing. Every control carrying loading={busy} is disabled the
    // instant the request starts, so the browser has already blurred the tap.
    createCheckin.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());

    await expectFocus(await screen.findByRole("alert"));
  });

  it("moves focus again on a SECOND identical failure", async () => {
    createCheckin.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());
    const alert = await screen.findByRole("alert");
    await expectFocus(alert);

    submitButton().focus();
    fireEvent.click(submitButton());

    await expectFocus(await screen.findByRole("alert"));
  });
});

// --- C13: the notice and the opt-in label must name the controller -----------

describe("CheckinPage collection notice", () => {
  it("renders the notice as visible text naming the boutique", async () => {
    await renderLoadedForm();

    const notice = screen.getByText(t("checkin.notice", { boutique: BOUTIQUE_NAME }));
    expect(notice).toBeVisible();
    expect(notice).toHaveTextContent(BOUTIQUE_NAME);
    // Not behind a disclosure: notice at the moment of collection means visible
    // at the moment of collection.
    expect(notice.closest("details")).toBeNull();
    expect(notice.closest("[aria-hidden='true']")).toBeNull();
  });

  it("renders the opt-in LABEL naming the boutique too", async () => {
    await renderLoadedForm();

    const label = t("checkin.optIn", { boutique: BOUTIQUE_NAME });
    expect(label).toContain(BOUTIQUE_NAME);
    expect(screen.getByLabelText(label)).toBe(screen.getByRole("checkbox"));
  });

  it("leaves NO {{boutique}} placeholder unrendered in either gated string", async () => {
    await renderLoadedForm();

    expect(screen.queryByText(/{{boutique}}/)).not.toBeInTheDocument();
  });

  it("withholds the WHOLE form while the boutique read is in flight", async () => {
    loadBoutique.mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(await screen.findByRole("status")).toHaveTextContent(t("checkin.loading"));
    expect(screen.queryByLabelText(t("checkin.name"))).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("checkin.submit") })).not.toBeInTheDocument();
  });

  it("withholds the WHOLE form when the boutique read failed, and says so", async () => {
    // Degrading to a nameless form is the one failure mode this arm exists to
    // prevent — a suspended tenant 404s and the read router's own budget can
    // 429 this independently of F33's three.
    loadBoutique.mockRejectedValue(new ApiError(404, "TENANT_NOT_FOUND", "No active boutique."));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(t("errors.tenantNotFound"));
    expect(screen.queryByLabelText(t("checkin.name"))).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("checkin.retry") })).toBeInTheDocument();
  });
});

// --- fields ------------------------------------------------------------------

describe("CheckinPage field wiring", () => {
  it("announces the phone format hint WITH the field", async () => {
    // Input folds `help` into aria-describedby, so it is announced with the
    // field rather than sitting beside it. The rejection this prevents happens
    // to a member of the public standing in a doorway.
    await renderLoadedForm();

    const described = phoneField().getAttribute("aria-describedby");
    expect(described).not.toBeNull();
    const hint = document.getElementById((described ?? "").split(" ")[0]);
    expect(hint).toHaveTextContent(t("checkin.phoneHint"));
  });

  it("keeps the submit above the 44px touch floor", async () => {
    // jsdom has no layout engine, so this is a class assertion by necessity:
    // size="sm" is min-h-9 (36px) and under the floor.
    await renderLoadedForm();
    expect(submitButton()).toHaveClass("min-h-11");
  });

  it("offers both visit types as one required radio group", async () => {
    await renderLoadedForm();

    expect(screen.getByRole("group", { name: t("checkin.visitType") })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).toBeRequired();
    }
  });
});

// --- the tab-scoped courtesy pointer ----------------------------------------

describe("CheckinPage recovery pointer", () => {
  it("renders the form, NO recovery link and issues no request on mount with no pointer", async () => {
    await renderLoadedForm();

    expect(screen.queryByRole("link", { name: t("checkin.lastFromDevice") })).not.toBeInTheDocument();
    // Zero server round-trip is the security property Ruling 1 depends on: a
    // helpful useEffect that "checked" the pointer would reintroduce a presence
    // lookup keyed by something other than the capability.
    expect(createCheckin).not.toHaveBeenCalled();
    expect(getQueuePosition).not.toHaveBeenCalled();
  });

  it("offers a link to the ticket and STILL issues no request when a pointer exists", async () => {
    window.sessionStorage.setItem("checkin:ticket", TICKET_ID);

    await renderLoadedForm();

    const link = screen.getByRole("link", { name: t("checkin.lastFromDevice") });
    expect(link).toHaveAttribute("href", `/q/${TICKET_ID}`);
    expect(getQueuePosition).not.toHaveBeenCalled();
    expect(createCheckin).not.toHaveBeenCalled();
  });

  it("labels the offer as the LAST CHECK-IN FROM THIS DEVICE, never as her position", async () => {
    // On a shared phone or a door tablet the slot holds someone else's ticket,
    // and a link labelled "your position" would hand a stranger a live
    // capability while claiming it was hers.
    window.sessionStorage.setItem("checkin:ticket", TICKET_ID);
    await renderLoadedForm();

    const link = screen.getByRole("link", { name: t("checkin.lastFromDevice") });
    expect(link).not.toHaveTextContent(t("checkin.positionLabel"));
    expect(link).not.toHaveTextContent(t("document.queuePosition"));
  });

  it("leaves the form fully usable underneath the offer — it is an offer, not a redirect", async () => {
    window.sessionStorage.setItem("checkin:ticket", TICKET_ID);
    await renderLoadedForm();

    expect(nameField()).toBeEnabled();
    expect(submitButton()).toBeEnabled();
    expect(window.location.pathname).toBe("/checkin");
  });

  it("OVERWRITES the pointer on a successful create", async () => {
    window.sessionStorage.setItem("checkin:ticket", "an-older-ticket");
    createCheckin.mockResolvedValue(ticket());
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.sessionStorage.getItem("checkin:ticket")).toBe(TICKET_ID);
    });
  });

  it("stores the ticket id and NOTHING else — no phone number is ever written", async () => {
    createCheckin.mockResolvedValue(ticket());
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());

    await waitFor(() => {
      expect(window.sessionStorage.getItem("checkin:ticket")).toBe(TICKET_ID);
    });
    expect(window.sessionStorage.length).toBe(1);
    for (const value of Object.values({ ...window.sessionStorage })) {
      expect(String(value)).not.toContain("0501234567");
      expect(String(value)).not.toContain("+972501234567");
    }
  });

  it("writes NOTHING when the create failed", async () => {
    createCheckin.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await renderLoadedForm();
    await fillValid();

    fireEvent.click(submitButton());
    await screen.findByRole("alert");

    expect(window.sessionStorage.getItem("checkin:ticket")).toBeNull();
  });
});

// --- C15: the two sentinels -------------------------------------------------

describe("CheckinPage leaves the Router's mount effects alone", () => {
  // Rendered in ISOLATION, never through <Router />: the Router's own effect
  // sets the title and focuses <main> one tick later, so an assertion made
  // through it could not fail no matter what this page wrote.
  it("does not touch document.title", async () => {
    const sentinel = "sentinel-title";
    document.title = sentinel;

    await renderLoadedForm();

    expect(document.title).toBe(sentinel);
  });

  it("does not move focus on mount", async () => {
    const anchor = document.createElement("button");
    document.body.appendChild(anchor);
    anchor.focus();

    await renderLoadedForm();

    // Synchronous, not polled: a polled negative passes on its first tick and
    // stops noticing a grab that lands later.
    expect(document.activeElement).toBe(anchor);
    anchor.remove();
  });
});

// --- accessibility ----------------------------------------------------------

describe("CheckinPage accessibility", () => {
  it("passes axe with zero violations on the loaded form", async () => {
    const { container } = await renderLoadedForm();

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations with every field in error", async () => {
    const { container } = await renderLoadedForm();
    fireEvent.click(submitButton());
    await screen.findByText(t("checkin.visitTypeRequired"));

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the withheld-form arm", async () => {
    loadBoutique.mockRejectedValue(new ApiError(404, "TENANT_NOT_FOUND", "No active boutique."));
    const { container } = renderPage();
    await screen.findByRole("alert");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);
});
