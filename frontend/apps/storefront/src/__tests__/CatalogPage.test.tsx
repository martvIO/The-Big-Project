import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { themeTokens } from "@boutique/ui";
import type { BoutiqueResponse, DressListResponse, StorefrontDress } from "../api";
import i18n from "../i18n";
import { StorefrontLayout } from "../components/StorefrontLayout";
import { CatalogPage } from "../routes/CatalogPage";

// Spread the real module so ApiError, errorMessage* and isNotFound keep their
// real implementations — the error copy under test is chosen by CODE mapping,
// and a stubbed mapper would assert nothing about it.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, listDresses: vi.fn(), getDress: vi.fn(), getBoutique: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const listDresses = vi.mocked(api.listDresses);
const loadBoutique = vi.mocked(getBoutiqueOnce);

// The server pins the page at 24 and the pilot ships ~60 dresses.
const PAGE_SIZE = 24;

// Open every day, same window: the header's "היום" line reads one fixed string
// whatever day the suite runs on, without faking the system clock.
const OPEN_ALL_WEEK = Array.from({ length: 7 }, (_, day) => ({
  day_of_week: day,
  open_time: "10:00:00",
  close_time: "19:00:00",
}));

// Sun–Thu only, so Friday and Saturday exercise the two closed branches.
// Jerusalem weekdays, verified: 24.12.2026 Thursday, 25.12 Friday, 26.12 Saturday.
const SUN_TO_THU = OPEN_ALL_WEEK.slice(0, 5);
const FRIDAY_IN_JERUSALEM = new Date("2026-12-25T10:00:00Z");
// Still Friday 25.12 in New York (the suite's TZ), already Saturday 26.12 in
// Jerusalem — the instant that tells the device clock from the boutique's.
const SATURDAY_IN_JERUSALEM = new Date("2026-12-25T22:30:00Z");

const DOWN = new ApiError(503, "UNKNOWN", "backend down");

function boutique(overrides: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: "שמלות כלה בעבודת יד",
    description: "בוטיק קטן ברחוב דיזנגוף.",
    phone: "052-1234567",
    address: "דיזנגוף 100, תל אביב",
    maps_url: null,
    instagram: "alma.bridal",
    hours: OPEN_ALL_WEEK,
    exceptions: [],
    ...overrides,
  };
}

function dress(overrides: Partial<StorefrontDress> = {}): StorefrontDress {
  return {
    id: "d1",
    name: "עלמה",
    price_agorot: 890000,
    reserved: false,
    cover: null,
    ...overrides,
  };
}

function listing(items: StorefrontDress[], total = items.length, offset = 0): DressListResponse {
  return { items, total, offset, limit: PAGE_SIZE };
}

// Zero-padded so "שמלה 25" is never a prefix of another card's name.
function catalogue(size: number): StorefrontDress[] {
  return Array.from({ length: size }, (_, index) =>
    dress({ id: `d${String(index + 1)}`, name: `שמלה ${String(index + 1).padStart(2, "0")}` }),
  );
}

function pending<T>(): Promise<T> {
  return new Promise<T>(() => {
    // never settles — holds the page in its loading state
  });
}

function renderCatalog(now?: Date) {
  // Routes read the boutique from the layout's single fetch, so the layout is
  // part of the unit under test — a bare <CatalogPage/> would render against a
  // context default that never resolves.
  return render(
    <StorefrontLayout>
      <CatalogPage now={now} />
    </StorefrontLayout>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("CatalogPage loading and error compositions", () => {
  it("holds the header slot with a skeleton while the boutique is in flight — never a placeholder name", async () => {
    loadBoutique.mockReturnValue(pending());
    listDresses.mockResolvedValue(listing([dress()]));

    const { container } = renderCatalog();
    await screen.findByRole("link", { name: /עלמה/ });

    // An h1 at all would mean a real header claiming an identity the boutique
    // has not sent — the fallback name is for a FAILED boutique, not a pending one.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.queryByText(i18n.t("catalog.essenceFallback"))).toBeNull();
    // Skeleton variant="text" lines={2}; the grid has already resolved.
    expect(container.querySelectorAll(".animate-skeleton")).toHaveLength(2);
  });

  it("paints six card skeletons under a real header while the collection is in flight", async () => {
    listDresses.mockReturnValue(pending());

    const { container } = renderCatalog();

    expect(
      await screen.findByRole("heading", { level: 1, name: "בוטיק אלמה" }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-skeleton")).toHaveLength(6);
  });

  it("keeps the identity it already fetched when only the collection fails, in ink-muted not danger", async () => {
    listDresses.mockRejectedValue(DOWN);

    renderCatalog();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("catalog.error"));
    // A backend that is down is not the boutique's fault.
    expect(alert.className).toContain("text-ink-muted");
    expect(alert.className).not.toContain("danger");
    // The boutique's own name, not the fallback: an h1 that merely exists
    // passes even on the defect this guards.
    expect(screen.getByRole("heading", { level: 1, name: "בוטיק אלמה" })).toBeInTheDocument();
    expect(screen.getByText(i18n.t("about.today", { hours: "10:00–19:00" }))).toBeInTheDocument();
    // Booking is a phone call — a dead collection must not take it down.
    expect(screen.getByRole("button", { name: i18n.t("booking.cta") })).toBeInTheDocument();
  });

  it("refetches the collection from the retry button", async () => {
    listDresses.mockRejectedValueOnce(DOWN).mockResolvedValue(listing([dress()]));

    renderCatalog();
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("catalog.retry") }));

    expect(await screen.findByRole("link", { name: /עלמה/ })).toBeInTheDocument();
    expect(listDresses).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("degrades to the error state with no booking CTA when identity itself fails", async () => {
    loadBoutique.mockRejectedValue(DOWN);
    listDresses.mockResolvedValue(listing([dress()]));

    renderCatalog();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("about.error"));
    // The heading SURVIVES the failure, carrying the fallback name. It is where
    // the skip link lands, and a page that loses its only h1 on an API error
    // drops a screen-reader user into an untitled region. axe does not catch
    // this (page-has-heading-one is best-practice, not A/AA), so it is pinned
    // here and again in the e2e suite.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      i18n.t("catalog.essenceFallback"),
    );
    // No phone, no address, nothing to put in the panel — the CTA would open empty.
    expect(screen.queryByRole("button", { name: i18n.t("booking.cta") })).toBeNull();
    expect(screen.getByRole("button", { name: i18n.t("catalog.retry") })).toBeInTheDocument();
  });

  it("recovers when the retry succeeds — the button is not inert", async () => {
    // The boutique block is fetched once by StorefrontLayout, so a retry wired
    // only to the dress list would leave a failed identity failed forever.
    loadBoutique.mockRejectedValueOnce(DOWN);
    listDresses.mockResolvedValue(listing([dress()]));

    renderCatalog();
    await screen.findByRole("alert");

    loadBoutique.mockResolvedValue(boutique());
    fireEvent.click(screen.getByRole("button", { name: i18n.t("catalog.retry") }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "בוטיק אלמה" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });
});

describe("CatalogPage load more", () => {
  it("appends the next page and drops the button once the collection is complete", async () => {
    const all = catalogue(50);
    listDresses.mockImplementation((offset = 0) =>
      Promise.resolve(listing(all.slice(offset, offset + PAGE_SIZE), all.length, offset)),
    );

    renderCatalog();
    await screen.findByRole("link", { name: /שמלה 01/ });

    // Dress 25 of 50 is unreachable without the button — the whole point of it.
    expect(screen.queryByRole("link", { name: /שמלה 25/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: i18n.t("catalog.more") }));

    expect(await screen.findByRole("link", { name: /שמלה 25/ })).toBeInTheDocument();
    // Offset is the number of items already held, not a page counter.
    expect(listDresses).toHaveBeenLastCalledWith(PAGE_SIZE);

    fireEvent.click(await screen.findByRole("button", { name: i18n.t("catalog.more") }));

    expect(await screen.findByRole("link", { name: /שמלה 50/ })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: i18n.t("catalog.more") })).toBeNull();
    });
    expect(screen.getAllByRole("link", { name: /שמלה/ })).toHaveLength(50);
  });

  it("keeps the dresses already on screen when the next page fails", async () => {
    const all = catalogue(50);
    listDresses
      .mockResolvedValueOnce(listing(all.slice(0, PAGE_SIZE), all.length))
      .mockRejectedValue(DOWN);

    renderCatalog();
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("catalog.more") }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("catalog.error"));
    // Losing the grid because page two timed out is the worse outcome.
    expect(screen.getAllByRole("link", { name: /שמלה/ })).toHaveLength(PAGE_SIZE);
    expect(screen.getByRole("link", { name: /שמלה 01/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /שמלה 24/ })).toBeInTheDocument();
  });
});

describe("CatalogPage grid", () => {
  it("renders a priced dress and a hidden-price dress side by side", async () => {
    listDresses.mockResolvedValue(
      listing([dress(), dress({ id: "d2", name: "נועה", price_agorot: null })]),
    );

    renderCatalog();

    const priced = await screen.findByRole("link", { name: /עלמה/ });
    expect(priced).toHaveTextContent("8,900");
    expect(priced).toHaveAttribute("href", "/dress/d1");

    const hidden = screen.getByRole("link", { name: /נועה/ });
    expect(within(hidden).getByText(i18n.t("catalog.priceOnRequest"))).toBeInTheDocument();
    // No number anywhere on the card — "hidden" and "never set" look identical.
    expect(hidden).not.toHaveTextContent(/\d/);
  });

  it("badges a reserved dress and keeps it browsable", async () => {
    listDresses.mockResolvedValue(listing([dress({ reserved: true })]));

    renderCatalog();

    const card = await screen.findByRole("link", { name: /עלמה/ });
    expect(within(card).getByText(i18n.t("catalog.reserved"))).toBeInTheDocument();
    expect(card).toHaveAttribute("href", "/dress/d1");
  });

  it("emits no <img> at all for a photo-less dress", async () => {
    listDresses.mockResolvedValue(listing([dress({ cover: null })]));

    renderCatalog();

    const card = await screen.findByRole("link", { name: /עלמה/ });
    // A broken-image icon in a bridal grid is worse than the monogram: the slot
    // must carry no <img> element whatsoever.
    expect(card.querySelectorAll("img")).toHaveLength(0);
    expect(within(card).getByText("ע")).toBeInTheDocument();
  });
});

describe("CatalogPage stale photo URLs", () => {
  const signed = {
    url: "https://storage.example/d1.jpg?sig=first",
    url_expires_at: "2026-07-27T10:15:00Z",
  };

  it("refetches once on a stale presigned URL, and never a second time", async () => {
    listDresses.mockResolvedValue(listing([dress({ cover: signed })]));

    renderCatalog();
    fireEvent.error(await screen.findByAltText("עלמה"));

    await waitFor(() => {
      expect(listDresses).toHaveBeenCalledTimes(2);
    });
    // A stale signature is not a missing photo — the <img> must survive.
    const img = await screen.findByAltText("עלמה");

    // An object that is genuinely gone would otherwise re-sign, re-fail, loop.
    fireEvent.error(img);
    expect(listDresses).toHaveBeenCalledTimes(2);
  });
});

describe("CatalogPage empty state", () => {
  it("stays a complete boutique with zero dresses — the state the pilot goes live in", async () => {
    listDresses.mockResolvedValue(listing([]));

    renderCatalog(FRIDAY_IN_JERUSALEM);

    expect(await screen.findByText(i18n.t("catalog.empty"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("catalog.emptyBody"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "בוטיק אלמה" })).toBeInTheDocument();
    // Hours and contact come along rather than a bare "nothing here yet".
    expect(screen.getByText(i18n.t("about.hoursHeading"))).toBeInTheDocument();

    // The booking modal holds a second, closed ContactPanel; the empty state's
    // own card is the one outside the <dialog>.
    const callLinks = screen
      .getAllByRole("link", { name: i18n.t("contact.call"), hidden: true })
      .filter((link) => link.closest("dialog") === null);
    expect(callLinks).toHaveLength(1);
    expect(callLinks[0]).toHaveAttribute("href", "tel:052-1234567");
  });

  // jsdom loads no stylesheet, so every class computes to the UA default and a
  // colour assertion would pass whichever class the line carried. Painting the
  // two real tokens is what gives it the power to fail.
  it("renders «הקולקציה בדרך» muted — it reports an absence, it is not the page's voice", async () => {
    listDresses.mockResolvedValue(listing([]));

    const sheet = document.createElement("style");
    sheet.textContent = `
      .text-ink { color: ${themeTokens["--color-ink"]}; }
      .text-ink-muted { color: ${themeTokens["--color-ink-muted"]}; }
    `;
    document.head.append(sheet);

    try {
      renderCatalog();
      const line = await screen.findByText(i18n.t("catalog.empty"));

      const probe = (className: string) => {
        const span = document.createElement("span");
        span.className = className;
        document.body.append(span);
        const { color } = getComputedStyle(span);
        span.remove();
        return color;
      };
      const ink = probe("text-ink");
      const muted = probe("text-ink-muted");
      // Guards the guard: an inert stylesheet would make both sides equal.
      expect(ink).not.toBe(muted);

      expect(getComputedStyle(line).color).toBe(muted);
    } finally {
      sheet.remove();
    }
  });
});

describe("CatalogPage hours line", () => {
  // jsdom loads no stylesheet, so every class computes to the same UA default
  // and a colour assertion would pass whichever class the line carried.
  // Painting the real tokens is what gives the assertion the power to fail.
  let sheet: HTMLStyleElement;

  beforeEach(() => {
    sheet = document.createElement("style");
    sheet.textContent = `
      .text-danger { color: ${themeTokens["--color-danger"]}; }
      .text-ink { color: ${themeTokens["--color-ink"]}; }
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

  function expectNotDanger(element: HTMLElement) {
    const danger = colourOf("text-danger");
    // Guards the guard: if the stylesheet were inert both sides would read the
    // same empty string and the comparison below could not fail.
    expect(danger).not.toBe(colourOf("text-ink-muted"));
    expect(getComputedStyle(element).color).toBe(colourOf("text-ink-muted"));
    expect(getComputedStyle(element).color).not.toBe(danger);
  }

  it("names the reopening day when closed today and tomorrow is closed too", async () => {
    listDresses.mockResolvedValue(listing([dress()]));
    loadBoutique.mockResolvedValue(boutique({ hours: SUN_TO_THU }));

    renderCatalog(FRIDAY_IN_JERUSALEM);

    // Friday: closed, and Saturday is closed as well, so the reopen is named
    // by weekday rather than as "tomorrow".
    const line = await screen.findByText(
      `${i18n.t("about.closedToday")} · ${i18n.t("about.opensOn", { day: "א׳", time: "10:00" })}`,
    );
    expectNotDanger(line);
  });

  it("says opens tomorrow when closed today — reading Jerusalem, not the device", async () => {
    listDresses.mockResolvedValue(listing([dress()]));
    loadBoutique.mockResolvedValue(boutique({ hours: SUN_TO_THU }));

    renderCatalog(SATURDAY_IN_JERUSALEM);

    // Saturday in Jerusalem, still Friday in New York. Reading the device clock
    // would render Friday's line — the named-day branch above — instead.
    const line = await screen.findByText(
      `${i18n.t("about.closedToday")} · ${i18n.t("about.opensTomorrow", { time: "10:00" })}`,
    );
    expectNotDanger(line);
  });

  it("omits the line entirely when the boutique has no weekly rules", async () => {
    listDresses.mockResolvedValue(listing([dress()]));
    loadBoutique.mockResolvedValue(boutique({ hours: [] }));

    renderCatalog(FRIDAY_IN_JERUSALEM);

    await screen.findByRole("heading", { level: 1, name: "בוטיק אלמה" });
    // No rules is the state every new tenant ships in — it is NOT "closed
    // today", and a header line reading "hours unknown" is worse than no line.
    expect(screen.queryByText(new RegExp(i18n.t("about.closedToday")))).toBeNull();
    expect(screen.queryByText(i18n.t("about.hoursUnavailable"))).toBeNull();
  });
});
