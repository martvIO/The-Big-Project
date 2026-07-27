import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@boutique/ui";
import { FALLBACK_ERROR_MESSAGE, resetBoutiqueCache } from "../api";
import type { PublicBoutiqueResponse, PublicDressDetailResponse } from "../api";
import i18n from "../i18n";
import { DressDetail } from "../pages/DressDetail";

// The page is exercised through a stubbed global fetch rather than a mocked
// api module: that keeps api.ts's real 404 -> ApiError path in the test, which
// is the branch the archived-dress state depends on.

const BOUTIQUE: PublicBoutiqueResponse = {
  name: "בוטיק ורד",
  profile: { phone: "052-1234567", address: "הרצל 1, תל אביב", description: null, maps_url: null },
  rules: [],
  exceptions: [],
};

function dressResponse(overrides: Partial<PublicDressDetailResponse> = {}): PublicDressDetailResponse {
  return {
    id: "d1",
    name: "ורד",
    description: null,
    price_agorot: 590000,
    reserved: false,
    variants: [],
    media: [],
    ...overrides,
  };
}

interface Reply {
  status: number;
  body: unknown;
}

let dressReply: Reply = { status: 200, body: dressResponse() };

const fetchMock = vi.fn((input: unknown) => {
  const url = String(input);
  const reply: Reply = url.includes("/storefront/boutique") ? { status: 200, body: BOUTIQUE } : dressReply;
  return Promise.resolve({
    ok: reply.status < 400,
    status: reply.status,
    json: () => Promise.resolve(reply.body),
  });
});

function dressFetchCount(): number {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes("/storefront/dresses/")).length;
}

function notFound(): Reply {
  return { status: 404, body: { error: { code: "NOT_FOUND", message: "לא נמצא" } } };
}

// The toast provider is real — the share fallback's confirmation is part of
// what the fallback promises.
async function renderDress(reply: Reply = { status: 200, body: dressResponse() }) {
  dressReply = reply;
  const result = render(
    <ToastProvider>
      <DressDetail dressId="d1" />
    </ToastProvider>,
  );
  // Every terminal state carries a back link; waiting on it means "the fetch
  // settled" without assuming which state won.
  await screen.findByRole("link", { name: i18n.t("nav.backToCatalog") });
  return result;
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockClear();
  resetBoutiqueCache();
  dressReply = { status: 200, body: dressResponse() };
  // The router owns the title in the real tree; here it stands in for the
  // placeholder Router would have set before the fetch landed.
  document.title = i18n.t("doc.dress");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DressDetail — the dress itself", () => {
  it("renders the name as the page's only h1, with the price and every size", async () => {
    await renderDress({
      status: 200,
      body: dressResponse({
        variants: [
          { size_label: "36", available: true },
          { size_label: "38", available: true },
        ],
      }),
    });

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("ורד");
    // The amount, not the currency glyph — formatting money is Price's job and
    // Price's test, and qa §11 whitelists the shekel sign by file.
    expect(screen.getByText(/5,900/)).toBeInTheDocument();
    expect(screen.getByText("36")).toBeInTheDocument();
    expect(screen.getByText("38")).toBeInTheDocument();
  });

  it("says an unavailable size is unavailable in words, never by colour alone", async () => {
    await renderDress({
      status: 200,
      body: dressResponse({
        variants: [
          { size_label: "36", available: true },
          { size_label: "38", available: false },
        ],
      }),
    });

    const chip = screen.getByText(new RegExp(i18n.t("size.unavailable")));
    expect(chip).toHaveTextContent("38");
    // The available size carries no marker — the absence is the signal.
    expect(screen.getByText("36")).not.toHaveTextContent(i18n.t("size.unavailable"));
  });

  it("renders the hidden-price label in the price slot", async () => {
    await renderDress({ status: 200, body: dressResponse({ price_agorot: null }) });

    expect(screen.getByText(i18n.t("price.hidden"))).toBeInTheDocument();
  });

  it("isolates a Latin-only name so RTL does not mangle it", async () => {
    await renderDress({ status: 200, body: dressResponse({ name: "Bella Rosa" }) });

    expect(screen.getByText("Bella Rosa")).toHaveAttribute("dir", "ltr");
  });

  it("keeps the booking CTA on a reserved dress — a fitting is still a conversation", async () => {
    await renderDress({ status: 200, body: dressResponse({ reserved: true }) });

    expect(screen.getByText(i18n.t("dress.reserved"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: i18n.t("booking.cta") })).toBeInTheDocument();
  });
});

describe("DressDetail — document title (WCAG 2.4.2, Level A)", () => {
  it("titles the tab with the dress name, so two dresses are not the same entry in history", async () => {
    await renderDress({ status: 200, body: dressResponse({ name: "ורד" }) });
    // The back link renderDress waits on exists in the loading state too, so
    // wait for the dress itself before reading the title it sets.
    await screen.findByRole("heading", { level: 1, name: "ורד" });

    expect(document.title).toBe("ורד");
    // The static route title is the pre-load placeholder, never the final one.
    expect(document.title).not.toBe(i18n.t("doc.dress"));
  });

  it("leaves the router's title alone when there is no dress to name", async () => {
    dressReply = notFound();
    render(
      <ToastProvider>
        <DressDetail dressId="gone" />
      </ToastProvider>,
    );
    await screen.findByText(i18n.t("dress.unavailable"));

    expect(document.title).toBe(i18n.t("doc.dress"));
  });
});

describe("DressDetail — description clamp", () => {
  const LONG = "שמלת משי בגזרת A עם מחוך רקום ידנית ושובל קצר. ".repeat(12).trim();

  it("clamps a long description and toggles the expander label", async () => {
    await renderDress({ status: 200, body: dressResponse({ description: LONG }) });

    expect(screen.getByText(LONG)).toHaveClass("line-clamp-6");

    fireEvent.click(screen.getByRole("button", { name: i18n.t("dress.more") }));

    expect(screen.getByText(LONG)).not.toHaveClass("line-clamp-6");
    expect(screen.getByRole("button", { name: i18n.t("dress.less") })).toBeInTheDocument();
  });

  it("offers no expander for a description that already fits", async () => {
    await renderDress({ status: 200, body: dressResponse({ description: "שמלת משי קצרה." }) });

    expect(screen.getByText("שמלת משי קצרה.")).not.toHaveClass("line-clamp-6");
    expect(screen.queryByRole("button", { name: i18n.t("dress.more") })).toBeNull();
  });
});

describe("DressDetail — photos", () => {
  it("hides the gallery chrome for a single photo", async () => {
    await renderDress({
      status: 200,
      body: dressResponse({ media: [{ url: "https://s3.test/a.jpg", url_expires_at: null }] }),
    });

    expect(screen.getAllByRole("img")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: i18n.t("gallery.previous") })).toBeNull();
    expect(screen.queryByRole("button", { name: i18n.t("gallery.next") })).toBeNull();
  });

  it("renders the monogram and emits no <img> at all when there is no photo", async () => {
    const { container } = await renderDress({ status: 200, body: dressResponse({ media: [] }) });

    // A broken-image glyph is the failure this state exists to prevent, so the
    // check is the absence of the element, not the absence of a src.
    expect(container.querySelectorAll("img")).toHaveLength(0);
    expect(screen.getByTestId("dress-monogram")).toHaveTextContent("ו");
  });

  it("drops a photo whose signed URL never got issued", async () => {
    await renderDress({
      status: 200,
      body: dressResponse({
        media: [
          { url: null, url_expires_at: null },
          { url: "https://s3.test/b.jpg", url_expires_at: null },
        ],
      }),
    });

    expect(screen.getAllByRole("img")).toHaveLength(1);
  });

  it("refetches once when a signed URL has gone stale — and only once", async () => {
    await renderDress({
      status: 200,
      body: dressResponse({ media: [{ url: "https://s3.test/a.jpg", url_expires_at: null }] }),
    });
    expect(dressFetchCount()).toBe(1);

    fireEvent.error(screen.getByRole("img", { name: "ורד" }));
    await waitFor(() => {
      expect(dressFetchCount()).toBe(2);
    });

    // A genuinely deleted object errors again on the fresh URL. One retry is
    // the ceiling; a second must not start a loop.
    await act(async () => {
      fireEvent.error(screen.getByRole("img", { name: "ורד" }));
      await Promise.resolve();
    });
    expect(dressFetchCount()).toBe(2);
  });
});

describe("DressDetail — states without a dress", () => {
  it("shows a skeleton, not an empty page, while the fetch is in flight", () => {
    dressReply = { status: 200, body: dressResponse() };
    render(
      <ToastProvider>
        <DressDetail dressId="d1" />
      </ToastProvider>,
    );

    expect(screen.getByTestId("dress-detail-loading")).toBeInTheDocument();
  });

  it("renders the unavailable copy for an archived or unknown id, with a working way back", async () => {
    dressReply = notFound();
    render(
      <ToastProvider>
        <DressDetail dressId="gone" />
      </ToastProvider>,
    );

    expect(await screen.findByText(i18n.t("dress.unavailable"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("dress.backToCatalog") })).toHaveAttribute("href", "/");
  });

  it("treats a malformed id as the same miss, instead of a Retry that repeats the 400 forever", async () => {
    // /dress/xyz out of a truncated or mistyped link fails the backend's UUID
    // coercion, which the platform normalises to 400 VALIDATION_ERROR. There is
    // no such dress, so retrying can only reproduce it.
    dressReply = { status: 400, body: { error: { code: "VALIDATION_ERROR", message: "bad id" } } };
    render(
      <ToastProvider>
        <DressDetail dressId="xyz" />
      </ToastProvider>,
    );

    expect(await screen.findByText(i18n.t("dress.unavailable"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: i18n.t("common.retry") })).toBeNull();
  });

  it("keeps a way back on a load failure too", async () => {
    dressReply = { status: 500, body: { error: { code: "INTERNAL", message: "boom" } } };
    render(
      <ToastProvider>
        <DressDetail dressId="d1" />
      </ToastProvider>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(i18n.t("dress.error"));
    expect(screen.getByRole("link", { name: i18n.t("dress.backToCatalog") })).toHaveAttribute("href", "/");
  });
});

describe("DressDetail — share", () => {
  afterEach(() => {
    Reflect.deleteProperty(navigator, "share");
    Reflect.deleteProperty(navigator, "clipboard");
  });

  it("copies the link when the browser has no share sheet", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await renderDress();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("dress.share") }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(window.location.href);
    });
    expect(await screen.findByText(i18n.t("dress.shareCopied"))).toBeInTheDocument();
  });

  it("prefers the native share sheet when the browser has one", async () => {
    const share = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "share", { value: share, configurable: true });
    await renderDress({ status: 200, body: dressResponse({ name: "ורד" }) });

    fireEvent.click(screen.getByRole("button", { name: i18n.t("dress.share") }));

    await waitFor(() => {
      expect(share).toHaveBeenCalledWith({ title: "ורד", url: window.location.href });
    });
  });

  it("says so instead of going inert when the browser can neither share nor copy", async () => {
    await renderDress();

    fireEvent.click(screen.getByRole("button", { name: i18n.t("dress.share") }));

    expect(await screen.findByRole("alert")).toHaveTextContent(FALLBACK_ERROR_MESSAGE);
  });
});
