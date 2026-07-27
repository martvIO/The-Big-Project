import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PublicBoutiqueResponse, PublicDress, PublicDressListResponse } from "../api";
import i18n from "../i18n";
import { Catalog } from "../pages/Catalog";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    api: { listDresses: vi.fn(), getDress: vi.fn(), getBoutique: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const listDresses = vi.mocked(api.listDresses);
const loadBoutique = vi.mocked(getBoutiqueOnce);

// Open every day, same window: the header's "היום" line then reads the same
// string whatever day the suite runs on, without faking the system clock.
const OPEN_ALL_WEEK = Array.from({ length: 7 }, (_, day) => ({
  day_of_week: day,
  open_time: "10:00:00",
  close_time: "19:00:00",
}));

// Sun–Thu only, so Friday and Saturday exercise the closed branch. Jerusalem
// weekdays, verified: 24.12.2026 Thursday, 25.12 Friday.
const SUN_TO_THU = Array.from({ length: 5 }, (_, day) => ({
  day_of_week: day,
  open_time: "10:00:00",
  close_time: "19:00:00",
}));
const THURSDAY = new Date("2026-12-24T10:00:00Z");
// Still Friday 25.12 in New York (the suite's TZ), already Saturday 26.12 in
// Jerusalem — the instant that tells the device clock from the boutique's.
const SATURDAY_IN_JERUSALEM = new Date("2026-12-25T22:30:00Z");

function boutique(overrides: Partial<PublicBoutiqueResponse> = {}): PublicBoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    profile: {
      phone: "052-1234567",
      address: "דיזנגוף 100, תל אביב",
      description: "בוטיק קטן ברחוב דיזנגוף.",
      maps_url: null,
    },
    rules: OPEN_ALL_WEEK,
    exceptions: [],
    ...overrides,
  };
}

function dress(overrides: Partial<PublicDress> = {}): PublicDress {
  return {
    id: "d1",
    name: "עלמה",
    price_agorot: 890000,
    reserved: false,
    cover: null,
    ...overrides,
  };
}

function listing(items: PublicDress[]): PublicDressListResponse {
  return { items, total: items.length, offset: 0, limit: 24 };
}

function pending<T>(): Promise<T> {
  return new Promise<T>(() => {
    // never settles — holds the page in its loading state
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("Catalog loading", () => {
  it("paints the identity header before the collection, then six card skeletons", () => {
    listDresses.mockReturnValue(pending());
    loadBoutique.mockReturnValue(pending());

    const { container } = render(<Catalog />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("brand.title"));
    expect(container.querySelectorAll(".animate-skeleton")).toHaveLength(6);
  });
});

describe("Catalog collection", () => {
  it("renders the boutique identity and one linked card per dress", async () => {
    listDresses.mockResolvedValue(
      listing([dress({ id: "d1", name: "עלמה" }), dress({ id: "d2", name: "נועה" })]),
    );

    render(<Catalog />);

    expect(await screen.findByRole("heading", { level: 1, name: "בוטיק אלמה" })).toBeInTheDocument();
    expect(screen.getByText(i18n.t("hours.today", { hours: "10:00–19:00" }))).toBeInTheDocument();
    expect(screen.getByText("דיזנגוף 100, תל אביב")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /עלמה/ })).toHaveAttribute("href", "/dress/d1");
    expect(screen.getByRole("link", { name: /נועה/ })).toHaveAttribute("href", "/dress/d2");
  });

  it("renders a hidden price as the agreed-price label, with no number anywhere on the card", async () => {
    listDresses.mockResolvedValue(listing([dress({ price_agorot: null })]));

    render(<Catalog />);

    const card = await screen.findByRole("link", { name: /עלמה/ });
    expect(within(card).getByText(i18n.t("price.hidden"))).toBeInTheDocument();
    expect(card).not.toHaveTextContent(/\d/);
  });

  it("badges a reserved dress and keeps it browsable", async () => {
    listDresses.mockResolvedValue(listing([dress({ reserved: true })]));

    render(<Catalog />);

    const card = await screen.findByRole("link", { name: /עלמה/ });
    expect(within(card).getByText(i18n.t("dress.reserved"))).toBeInTheDocument();
    expect(card).toHaveAttribute("href", "/dress/d1");
  });

  it("upgrades a card tap to a client navigation", async () => {
    listDresses.mockResolvedValue(listing([dress()]));

    render(<Catalog />);
    const card = await screen.findByRole("link", { name: /עלמה/ });

    expect(fireEvent.click(card, { button: 0 })).toBe(false); // preventDefault() ran
    expect(window.location.pathname).toBe("/dress/d1");
  });

  it("lets a meta-click through so a card still opens in a new tab", async () => {
    listDresses.mockResolvedValue(listing([dress()]));

    render(<Catalog />);
    const card = await screen.findByRole("link", { name: /עלמה/ });

    expect(fireEvent.click(card, { button: 0, metaKey: true })).toBe(true);
    expect(window.location.pathname).toBe("/");
  });
});

describe("Catalog stale photo URLs", () => {
  const signed = {
    url: "https://storage.example/d1.jpg?sig=first",
    url_expires_at: "2026-07-27T10:15:00Z",
  };

  it("refetches once when a presigned URL goes stale, and never falls back to the monogram", async () => {
    listDresses.mockResolvedValue(listing([dress({ cover: signed })]));

    render(<Catalog />);
    fireEvent.error(await screen.findByAltText("עלמה"));

    await waitFor(() => {
      expect(listDresses).toHaveBeenCalledTimes(2);
    });
    // A stale signature is not a missing photo — the <img> must survive.
    expect(await screen.findByAltText("עלמה")).toBeInTheDocument();
  });

  it("does not loop when the object is genuinely gone", async () => {
    listDresses.mockResolvedValue(listing([dress({ cover: signed })]));

    render(<Catalog />);
    fireEvent.error(await screen.findByAltText("עלמה"));
    await waitFor(() => {
      expect(listDresses).toHaveBeenCalledTimes(2);
    });

    fireEvent.error(await screen.findByAltText("עלמה"));
    expect(listDresses).toHaveBeenCalledTimes(2);
  });
});

describe("Catalog empty state", () => {
  it("stays a complete boutique with zero dresses — the state the pilot goes live in", async () => {
    listDresses.mockResolvedValue(listing([]));

    render(<Catalog />);

    expect(await screen.findByText(i18n.t("catalog.empty.title"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "בוטיק אלמה" })).toBeInTheDocument();
    // The shared identity block, not a blank grid: the story and the hours card
    // come along. (Contact wiring is asserted in the booking-CTA suite — the
    // closed dialog holds a second, hidden ContactPanel.)
    expect(screen.getByText("בוטיק קטן ברחוב דיזנגוף.")).toBeInTheDocument();
    expect(screen.getByText(i18n.t("hours.heading"))).toBeInTheDocument();
  });
});

describe("Catalog hours line", () => {
  // The header's "היום:" line renders on / — not only on /about — and it is the
  // string a visitor to an appointment-only boutique acts on. Both day-check
  // branches, against a frozen clock, under TZ=America/New_York.
  it("reads today's window on an open day", async () => {
    listDresses.mockResolvedValue(listing([dress()]));
    loadBoutique.mockResolvedValue(boutique({ rules: SUN_TO_THU }));

    render(<Catalog now={THURSDAY} />);

    expect(
      await screen.findByText(i18n.t("hours.today", { hours: "10:00–19:00" })),
    ).toBeInTheDocument();
  });

  it("says closed today and names the reopen on a closed day — reading Jerusalem, not the device", async () => {
    listDresses.mockResolvedValue(listing([dress()]));
    loadBoutique.mockResolvedValue(boutique({ rules: SUN_TO_THU }));

    render(<Catalog now={SATURDAY_IN_JERUSALEM} />);

    // Saturday in Jerusalem (Friday in New York): closed, reopening Sunday, i.e.
    // tomorrow. Reading the device clock would render Friday's line instead.
    expect(
      await screen.findByText(
        `${i18n.t("hours.closedToday")} · ${i18n.t("hours.opensTomorrow", { time: "10:00" })}`,
      ),
    ).toBeInTheDocument();
  });
});

describe("Catalog error state", () => {
  it("keeps the identity it already fetched and offers a retry instead of a blank page", async () => {
    // Only the collection failed. The boutique answered, so nothing about the
    // identity block may fall back — Promise.all would have thrown it away.
    listDresses.mockRejectedValue(new ApiError(503, "UNKNOWN", "backend down"));

    render(<Catalog />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("catalog.error"));
    // The boutique's own name, not brand.title: an h1 that merely exists passed
    // on the defect this guards.
    expect(screen.getByRole("heading", { level: 1, name: "בוטיק אלמה" })).toBeInTheDocument();
    expect(screen.getByText(i18n.t("hours.today", { hours: "10:00–19:00" }))).toBeInTheDocument();
    expect(screen.getByText("דיזנגוף 100, תל אביב")).toBeInTheDocument();
    // Booking is a phone call — a dead collection must not take it down.
    expect(screen.getByRole("button", { name: i18n.t("booking.cta") })).toBeInTheDocument();
  });

  it("falls back to the brand name only when the boutique itself is unreachable", async () => {
    listDresses.mockRejectedValue(new ApiError(503, "UNKNOWN", "backend down"));
    loadBoutique.mockRejectedValue(new ApiError(503, "UNKNOWN", "backend down"));

    render(<Catalog />);

    await screen.findByRole("alert");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(i18n.t("brand.title"));
    expect(screen.queryByRole("button", { name: i18n.t("booking.cta") })).toBeNull();
  });

  it("reloads the collection from the retry button", async () => {
    listDresses
      .mockRejectedValueOnce(new ApiError(503, "UNKNOWN", "backend down"))
      .mockResolvedValue(listing([dress()]));

    render(<Catalog />);
    fireEvent.click(await screen.findByRole("button", { name: i18n.t("common.retry") }));

    expect(await screen.findByRole("link", { name: /עלמה/ })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("Catalog booking CTA", () => {
  it("renders exactly one CTA and opens the contact panel from it", async () => {
    listDresses.mockResolvedValue(listing([dress()]));

    render(<Catalog />);
    const cta = await screen.findByRole("button", { name: i18n.t("booking.cta") });
    // One instance covers both breakpoints — the bar is fixed below 768 and
    // static from 768 up. A second instance would double it at one of them.
    expect(screen.getAllByRole("button", { name: i18n.t("booking.cta") })).toHaveLength(1);

    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).not.toHaveAttribute("open");

    fireEvent.click(cta);

    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getByText(i18n.t("contact.call"))).toHaveAttribute("href", "tel:052-1234567");
    expect(within(dialog).getByText(i18n.t("contact.whatsapp"))).toHaveAttribute(
      "href",
      "https://wa.me/972521234567",
    );
  });
});
