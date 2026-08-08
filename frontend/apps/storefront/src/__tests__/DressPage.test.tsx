import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, getBoutiqueOnce } from "../api";
import type { BoutiqueResponse, StorefrontDetail, StorefrontMedia } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { DressPage } from "../routes/DressPage";
import { PRIVACY_FIXTURE } from "../test/boutique";

// ApiError, isNotFound and errorMessageOr stay REAL: the archived-dress branch
// and the "never render the server's English message" rule are what half this
// file asserts, and mocking them would assert the mock instead.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { listDresses: vi.fn(), getDress: vi.fn(), getBoutique: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const getDress = vi.mocked(api.getDress);
const loadBoutique = vi.mocked(getBoutiqueOnce);

// A different first letter from the dress's, so the monogram test can tell
// which name it rendered. No instagram: the footer would otherwise add links
// that have nothing to do with the dress.
const BOUTIQUE: BoutiqueResponse = {
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
};

function photo(url: string | null): StorefrontMedia {
  return { url, url_expires_at: null };
}

function dress(overrides: Partial<StorefrontDetail> = {}): StorefrontDetail {
  return {
    id: "d1",
    name: "ורד",
    description: null,
    price_agorot: 590000,
    reserved: false,
    sizes: [],
    media: [],
    unavailable_ranges: [],
    ...overrides,
  };
}

function imageOf(n: number, total: number): string {
  return i18n.t("gallery.imageOf", { n, total });
}

function pending<T>(): Promise<T> {
  return new Promise<T>(() => {
    // never settles — holds the page in its loading state
  });
}

// Routes read the boutique from the layout-level fetch, so the layout is part
// of the unit under test, not scaffolding around it.
function renderDress(dressId = "d1") {
  return render(
    <StorefrontLayout>
      <DressPage dressId={dressId} />
    </StorefrontLayout>,
  );
}

async function renderLoaded(detail: StorefrontDetail) {
  getDress.mockResolvedValue(detail);
  const utils = renderDress(detail.id);
  await screen.findByRole("heading", { level: 1, name: detail.name });
  // findBy resolves on the first commit, before the passive effects that commit
  // scheduled have run — and DescriptionClamp decides whether to show its toggle
  // in one of them. Without this flush the clamp assertions race the measurement.
  await act(async () => {});
  return utils;
}

// jsdom reports scrollHeight = clientHeight = 0 for every element, so
// DescriptionClamp's measured overflow can never fire on its own.
function stubMetrics(scrollHeight: number, clientHeight: number) {
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    value: scrollHeight,
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    value: clientHeight,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(BOUTIQUE);
  getDress.mockResolvedValue(dress());
  window.history.replaceState(null, "", "/dress/d1");
  // Router owns the title in the real tree; this stands in for the placeholder
  // it sets before the dress name is knowable.
  document.title = i18n.t("document.dress");
});

afterEach(() => {
  Reflect.deleteProperty(HTMLElement.prototype, "scrollHeight");
  Reflect.deleteProperty(HTMLElement.prototype, "clientHeight");
});

describe("DressPage — the way back", () => {
  it("offers a real <a href='/'> while the dress is still loading", () => {
    getDress.mockReturnValue(pending<StorefrontDetail>());
    loadBoutique.mockReturnValue(pending<BoutiqueResponse>());
    renderDress();

    expect(screen.getByTestId("dress-detail-loading")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("dress.back") })).toHaveAttribute("href", "/");
  });

  it("offers it on the loaded dress", async () => {
    await renderLoaded(dress());

    expect(screen.getByRole("link", { name: i18n.t("dress.back") })).toHaveAttribute("href", "/");
  });
});

describe("DressPage — the gallery", () => {
  it("names the main photo by its POSITION, never by the dress name", async () => {
    await renderLoaded(
      dress({
        name: "ורד",
        media: [photo("https://s3.test/a.jpg"), photo("https://s3.test/b.jpg"), photo("https://s3.test/c.jpg")],
      }),
    );

    expect(screen.getByRole("img", { name: imageOf(1, 3) })).toHaveAttribute(
      "src",
      "https://s3.test/a.jpg",
    );
    // Three photos all named "ורד" give a screen-reader user three identical
    // strings with no way to tell them apart. The CARD's alt is the dress name;
    // the detail gallery's is not.
    expect(screen.queryByRole("img", { name: "ורד" })).toBeNull();
    // The thumbnails are alt="" decoration, so the position string is the only
    // accessible image name on the page.
    expect(screen.getAllByRole("img")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: i18n.t("gallery.next") }));

    expect(screen.getByRole("img", { name: imageOf(2, 3) })).toHaveAttribute(
      "src",
      "https://s3.test/b.jpg",
    );
  });

  it("hides the chrome for a single photo", async () => {
    await renderLoaded(dress({ media: [photo("https://s3.test/a.jpg")] }));

    expect(screen.getByRole("img", { name: imageOf(1, 1) })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: i18n.t("gallery.previous") })).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("gallery.next") })).toBeNull();
  });

  it("numbers positions AFTER dropping a photo whose signed URL never got issued", async () => {
    await renderLoaded(dress({ media: [photo(null), photo("https://s3.test/b.jpg")] }));

    // "1 of 1", not "2 of 2": an unusable photo must not consume a position, or
    // the spoken count stops matching what the visitor can page through.
    expect(screen.getByRole("img", { name: imageOf(1, 1) })).toHaveAttribute(
      "src",
      "https://s3.test/b.jpg",
    );
    expect(screen.getAllByRole("img")).toHaveLength(1);
  });

  it("refetches once when a signed URL has gone stale — and only once", async () => {
    await renderLoaded(dress({ media: [photo("https://s3.test/a.jpg")] }));
    expect(getDress).toHaveBeenCalledTimes(1);

    fireEvent.error(screen.getByRole("img", { name: imageOf(1, 1) }));
    await waitFor(() => {
      expect(getDress).toHaveBeenCalledTimes(2);
    });

    // A genuinely deleted object errors again on the fresh URL. One retry is the
    // ceiling; a second must not start a loop.
    await act(async () => {
      fireEvent.error(screen.getByRole("img", { name: imageOf(1, 1) }));
      await Promise.resolve();
    });
    expect(getDress).toHaveBeenCalledTimes(2);
  });

  it("draws the BOUTIQUE's initial, not the dress's, when there is no photo", async () => {
    const { container } = await renderLoaded(dress({ name: "ורד", media: [] }));

    // aria-hidden decoration next to the <h1> that already says the name — a
    // test id is the only handle, by design.
    await waitFor(() => {
      expect(screen.getByTestId("dress-monogram")).toHaveTextContent("ב");
    });
    expect(screen.getByTestId("dress-monogram")).not.toHaveTextContent("ו");
    // A broken-image glyph is the failure this state exists to prevent, so the
    // check is the absence of the element, not the absence of a src.
    expect(container.querySelectorAll("img")).toHaveLength(0);
  });
});

describe("DressPage — the facts column", () => {
  it("renders the name as the only h1, with the price", async () => {
    await renderLoaded(dress({ name: "ורד", price_agorot: 590000 }));

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    // The amount, not the currency glyph — formatting money is Price's job.
    expect(screen.getByText(/5,900/)).toBeInTheDocument();
  });

  it("fills the price slot with the on-request label when the price is hidden", async () => {
    await renderLoaded(dress({ price_agorot: null }));

    expect(screen.getByText(i18n.t("catalog.priceOnRequest"))).toBeInTheDocument();
  });

  it("isolates a Latin-only name so RTL does not mangle it", async () => {
    await renderLoaded(dress({ name: "Bella Rosa" }));

    expect(screen.getByText("Bella Rosa")).toHaveAttribute("dir", "ltr");
  });

  it("says an unavailable size in WORDS, never by dimming alone", async () => {
    await renderLoaded(
      dress({
        sizes: [
          { size_label: "36", available: true },
          { size_label: "38", available: false },
        ],
      }),
    );

    expect(screen.getByText(i18n.t("dress.unavailable"))).toBeInTheDocument();
    expect(screen.getByText("38").closest("li")).toHaveTextContent(i18n.t("dress.unavailable"));
    expect(screen.getByText("36").closest("li")).toHaveTextContent(i18n.t("dress.available"));
  });

  it("keeps the booking CTA usable on a reserved dress, carrying the dress id", async () => {
    await renderLoaded(dress({ reserved: true }));

    expect(screen.getByText(i18n.t("dress.reserved"))).toBeInTheDocument();
    // The href, not toBeEnabled(): jest-dom's disabled matchers apply only to
    // button/input/select/textarea/optgroup/option/fieldset, so toBeEnabled()
    // on an <a> asserts nothing at all. The dress id is D9's path SEGMENT — the
    // navigation store snapshots pathname only and cannot see a query string.
    expect(screen.getByRole("link", { name: i18n.t("booking.cta") })).toHaveAttribute(
      "href",
      "/book/slot/d1",
    );
  });

  // --- F28: the booked-out dates block ---

  it("renders no heading at all when the dress has no reservations", async () => {
    await renderLoaded(dress());

    expect(screen.queryByText(i18n.t("dress.reservedDatesHeading"))).not.toBeInTheDocument();
    expect(screen.queryByText(i18n.t("dress.reservedDatesNote"))).not.toBeInTheDocument();
  });

  it("states the ranges and the fittings note, and keeps the CTA usable", async () => {
    await renderLoaded(
      dress({
        unavailable_ranges: [
          { starts_on: "2026-08-12", ends_on: "2026-08-18" },
          { starts_on: "2026-12-28", ends_on: "2027-01-02" },
        ],
      }),
    );

    expect(screen.getByText(i18n.t("dress.reservedDatesHeading"))).toBeInTheDocument();
    // Same-month collapses to one numeral island; cross-year splits into two.
    expect(screen.getByText("12–18")).toBeInTheDocument();
    expect(screen.getByText("28 בדצמבר")).toBeInTheDocument();
    expect(screen.getByText("2 בינואר 2027")).toBeInTheDocument();
    // Q9 spelled as copy — the line that keeps the CTA honest.
    expect(screen.getByText(i18n.t("dress.reservedDatesNote"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("booking.cta") })).toHaveAttribute(
      "href",
      "/book/slot/d1",
    );
  });

  it("wraps every numeral run in a bdi island", async () => {
    await renderLoaded(
      dress({ unavailable_ranges: [{ starts_on: "2026-08-12", ends_on: "2026-08-18" }] }),
    );

    // R19: an unisolated numeral run reorders around neighbouring RTL text.
    expect(screen.getByText("12–18").tagName).toBe("BDI");
  });

  it("states the dates without announcing them — nothing happened", async () => {
    await renderLoaded(
      dress({ unavailable_ranges: [{ starts_on: "2026-08-12", ends_on: "2026-08-18" }] }),
    );

    const heading = screen.getByText(i18n.t("dress.reservedDatesHeading"));
    const block = heading.closest("div");
    expect(block).not.toBeNull();
    expect(block?.querySelector("[role='alert']")).toBeNull();
    expect(block?.querySelector("[role='status']")).toBeNull();
  });
});

describe("DressPage — description clamp", () => {
  const LONG = "שמלת משי בגזרת A עם מחוך רקום ידנית ושובל קצר. ".repeat(12).trim();

  it("wires the toggle to the paragraph and flips aria-expanded", async () => {
    stubMetrics(500, 100);
    await renderLoaded(dress({ description: LONG }));

    expect(screen.getByText(LONG)).toHaveClass("line-clamp-6");

    const toggle = screen.getByRole("button", { name: i18n.t("dress.more") });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    const controls = toggle.getAttribute("aria-controls") ?? "";
    // aria-controls has to point AT the clamped paragraph — a dangling id is
    // invisible in the rendered page and useless to assistive tech.
    expect(document.getElementById(controls)).toHaveTextContent(LONG);

    fireEvent.click(toggle);

    const expanded = screen.getByRole("button", { name: i18n.t("dress.less") });
    expect(expanded).toHaveAttribute("aria-expanded", "true");
    expect(expanded).toHaveAttribute("aria-controls", controls);
    expect(screen.getByText(LONG)).not.toHaveClass("line-clamp-6");
  });

  it("offers no toggle for a description that already fits", async () => {
    // Same metrics stub, no overflow: this asserts the MEASUREMENT, not jsdom's
    // zeros, so a component that always renders the toggle fails here.
    stubMetrics(100, 100);
    await renderLoaded(dress({ description: "שמלת משי קצרה." }));

    expect(screen.queryByRole("button", { name: i18n.t("dress.more") })).toBeNull();
  });
});

describe("DressPage — states without a dress", () => {
  it("renders the unavailable copy for an archived or unknown id, with a way back and no Retry", async () => {
    getDress.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    renderDress("gone");

    expect(await screen.findByText(i18n.t("dress.unavailableDress"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("dress.backToCatalog") })).toHaveAttribute(
      "href",
      "/",
    );
    // Retrying a 404 just repeats it — an archived dress is gone for good.
    expect(screen.queryByRole("button", { name: i18n.t("catalog.retry") })).toBeNull();
    // Every backend message is English; this page is Hebrew-only.
    expect(screen.queryByText(/Resource not found/)).toBeNull();
  });

  it("treats a malformed id as the same miss, not a Retry that repeats the 400 forever", async () => {
    getDress.mockRejectedValue(new ApiError(400, "VALIDATION_ERROR", "Invalid uuid."));
    renderDress("xyz");

    expect(await screen.findByText(i18n.t("dress.unavailableDress"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: i18n.t("catalog.retry") })).toBeNull();
  });

  it("offers Hebrew error copy, a way back and a working Retry on a non-404 failure", async () => {
    getDress.mockRejectedValue(new ApiError(500, "INTERNAL", "Something exploded."));
    renderDress();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("dress.error"));
    expect(alert).not.toHaveTextContent("Something exploded.");
    expect(screen.getByRole("link", { name: i18n.t("dress.back") })).toHaveAttribute("href", "/");

    getDress.mockResolvedValue(dress({ name: "ורד" }));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("catalog.retry") }));

    expect(await screen.findByRole("heading", { level: 1, name: "ורד" })).toBeInTheDocument();
  });
});

// The <h1> is where the skip link lands and what orients a screen-reader user.
// axe passes a heading-less page — page-has-heading-one is best-practice, not
// A/AA — so every state is asserted by hand here.
describe("DressPage — one h1 in every state", () => {
  function soleHeading(): HTMLElement {
    const main = screen.getByRole("main");
    expect(within(main).getAllByRole("heading", { level: 1 })).toHaveLength(1);
    return within(main).getByRole("heading", { level: 1 });
  }

  it("titles the skeleton with the brand fallback while both fetches are in flight", () => {
    getDress.mockReturnValue(pending<StorefrontDetail>());
    loadBoutique.mockReturnValue(pending<BoutiqueResponse>());
    renderDress();

    expect(soleHeading()).toHaveTextContent(i18n.t("catalog.essenceFallback"));
  });

  it("names the boutique on an archived dress instead of dropping the only heading", async () => {
    getDress.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    renderDress("gone");
    await screen.findByText(i18n.t("dress.unavailableDress"));

    await waitFor(() => {
      expect(soleHeading()).toHaveTextContent(BOUTIQUE.name);
    });
  });

  it("keeps the heading on a non-404 failure, above the alert", async () => {
    getDress.mockRejectedValue(new ApiError(500, "INTERNAL", "Something exploded."));
    renderDress();
    await screen.findByRole("alert");

    await waitFor(() => {
      expect(soleHeading()).toHaveTextContent(BOUTIQUE.name);
    });
  });

  it("hands the heading over to the dress once it loads", async () => {
    await renderLoaded(dress({ name: "ורד" }));

    expect(soleHeading()).toHaveTextContent("ורד");
  });
});

describe("DressPage — document title (WCAG 2.4.2, Level A)", () => {
  it("titles the tab with the dress name, so two dresses are not one entry in history", async () => {
    await renderLoaded(dress({ name: "ורד" }));

    await waitFor(() => {
      expect(document.title).toBe("ורד");
    });
    // The static route title is the pre-load placeholder, never the final one.
    expect(document.title).not.toBe(i18n.t("document.dress"));
  });

  it("leaves the router's placeholder alone when there is no dress to name", async () => {
    getDress.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    renderDress("gone");
    await screen.findByText(i18n.t("dress.unavailableDress"));

    expect(document.title).toBe(i18n.t("document.dress"));
  });
});
