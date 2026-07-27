import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { resetBoutiqueCache } from "../api";
import type { PublicBoutiqueResponse } from "../api";
import { About } from "../pages/About";

const NAME = "אטלייה לבן";
const STORY = "התחלנו בחדר אחד ברחוב דיזנגוף, עם שמלה אחת ושתי ידיים.";
const ADDRESS = "רח׳ דיזנגוף 99, תל אביב";

const FULL: PublicBoutiqueResponse = {
  name: NAME,
  profile: {
    phone: "052-1234567",
    address: ADDRESS,
    description: STORY,
    maps_url: "https://maps.google.com/?q=dizengoff+99",
  },
  // Saturday and Tuesday carry no rule on purpose — HoursTable must still
  // account for them with the literal "סגור".
  rules: [
    { day_of_week: 0, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 1, open_time: "10:00:00", close_time: "19:00:00" },
    { day_of_week: 5, open_time: "09:00:00", close_time: "13:00:00" },
  ],
  exceptions: [],
};

function withProfile(patch: Partial<PublicBoutiqueResponse["profile"]>): PublicBoutiqueResponse {
  return { ...FULL, profile: { ...FULL.profile, ...patch } };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// A Response body is single-use — hand out a fresh one per fetch call.
function stubFetch(makeResponse: () => Response) {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(makeResponse()));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  // The boutique promise is module-level and outlives a test's render.
  resetBoutiqueCache();
});

describe("About — default", () => {
  it("renders the story, the whole week's hours and the contact channels", async () => {
    stubFetch(() => jsonResponse(200, FULL));
    render(<About />);

    expect(await screen.findByText(STORY)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(NAME);
    expect(screen.getByRole("heading", { level: 2, name: "שעות פעילות" })).toBeInTheDocument();

    // Saturday has no rule and must still render, labelled closed.
    const saturday = screen.getByRole("rowheader", { name: "שבת" });
    expect(saturday.parentElement).toHaveTextContent("סגור");

    expect(screen.getByRole("link", { name: "חיוג" })).toHaveAttribute("href", "tel:052-1234567");
    expect(screen.getByRole("link", { name: "וואטסאפ" })).toHaveAttribute(
      "href",
      "https://wa.me/972521234567",
    );
  });

  it("links the address to the map when the owner supplied one", async () => {
    stubFetch(() => jsonResponse(200, FULL));
    render(<About />);

    const link = await screen.findByRole("link", { name: ADDRESS });
    expect(link).toHaveAttribute("href", "https://maps.google.com/?q=dizengoff+99");
  });
});

describe("About — sparse profile", () => {
  it("collapses the story row when the owner has not written one, hours still render", async () => {
    stubFetch(() => jsonResponse(200, withProfile({ description: null })));
    render(<About />);

    expect(await screen.findByRole("heading", { level: 2, name: "שעות פעילות" })).toBeInTheDocument();
    expect(screen.queryByText(STORY)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חיוג" })).toBeInTheDocument();
  });

  it("renders the address as plain text when there is no maps_url — never a dead link", async () => {
    stubFetch(() => jsonResponse(200, withProfile({ maps_url: null })));
    render(<About />);

    // closest("a"), not queryByRole("link"): an <a> with no href has no link
    // role, so a role query passes on the very defect this guards against.
    expect((await screen.findByText(ADDRESS)).closest("a")).toBeNull();
    // The Google Maps row goes with it rather than pointing nowhere.
    expect(screen.queryByRole("link", { name: "פתיחה ב-Google Maps" })).not.toBeInTheDocument();
  });
});

describe("About — booking CTA", () => {
  it("ships one static inline button and no fixed bar at any width", async () => {
    stubFetch(() => jsonResponse(200, FULL));
    const { container } = render(<About />);

    const cta = await screen.findAllByRole("button", { name: "קביעת תור למדידה" });
    expect(cta).toHaveLength(1);
    // BookingCTA's bar is position:fixed below 768. /about renders nothing
    // fixed — the design gives it a static inline button instead (qa §7), and
    // shipping both is two visible CTAs.
    expect(container.querySelectorAll(".fixed")).toHaveLength(0);
    expect(cta[0].closest(".fixed")).toBeNull();
  });

  it("opens the booking panel so the button is not decorative", async () => {
    stubFetch(() => jsonResponse(200, FULL));
    render(<About />);

    fireEvent.click(await screen.findByRole("button", { name: "קביעת תור למדידה" }));
    expect(screen.getByRole("heading", { name: "לקביעת תור, דברו איתנו" })).toBeInTheDocument();
  });
});

describe("About — loading and error", () => {
  it("paints the identity and skeletons while loading, never a blank column", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => new Promise<Response>(() => undefined)),
    );
    const { container } = render(<About />);

    // Before the name arrives the heading falls back to the brand title, so the
    // hairline and h1 never pop in late.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("חנות הכלות");
    // Skeleton is aria-hidden by design, so its animation class is the handle.
    expect(container.querySelectorAll(".animate-skeleton").length).toBeGreaterThan(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the identity and offers a retry when the boutique cannot load", async () => {
    stubFetch(() => jsonResponse(503, { error: { code: "UNAVAILABLE", message: "nope" } }));
    render(<About />);

    const alert = await screen.findByRole("alert");
    // Our Hebrew copy, not the backend's message — one voice on the public side.
    expect(alert).toHaveTextContent("לא הצלחנו לטעון את פרטי הבוטיק כרגע.");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("חנות הכלות");
    expect(screen.getByRole("button", { name: "נסי שוב" })).toBeInTheDocument();
  });

  it("actually refetches on retry — the shared boutique promise must not cache the failure", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() =>
        Promise.resolve(jsonResponse(503, { error: { code: "X", message: "y" } })),
      )
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(200, FULL)));
    vi.stubGlobal("fetch", fetchMock);
    render(<About />);

    fireEvent.click(await screen.findByRole("button", { name: "נסי שוב" }));

    expect(await screen.findByText(STORY)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
