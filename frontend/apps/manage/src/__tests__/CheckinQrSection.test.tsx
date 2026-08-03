import { fireEvent, render, screen } from "@testing-library/react";
import { run } from "axe-core";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { CheckinQrSection } from "../components/CheckinQrSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: { getCheckinQr: vi.fn() },
  };
});

const { api } = await import("../api");
const getCheckinQr = vi.mocked(api.getCheckinQr);

const CHECKIN_URL = "https://bella.modryn.co.il/checkin";
// The shape the server actually returns (verified in test_checkin_qr_api.py):
// no XML declaration, and the namespace present — an SVG without xmlns renders
// BLANK through a data: URI, which is the failure this fixture keeps visible.
const SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="37" height="37" class="segno">' +
  '<path class="qrline" stroke="#000" d="M4 4.5h7m2 0h1"/></svg>';

const DATA_PREFIX = "data:image/svg+xml;utf8,";

// The section renders inside ConsoleShell's <main>, which owns the console's
// single sr-only <h1>. The axe harness reproduces that frame rather than
// scanning a headless fragment (the StaffSection/GatewaySection precedent).
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getCheckinQr.mockResolvedValue({ checkin_url: CHECKIN_URL, qr_svg: SVG });
});

describe("the printable check-in code", () => {
  it("renders the URL as selectable text beside the code", async () => {
    // A printed QR with no legible URL next to it strands anyone whose camera
    // fails, and the poster is the only copy she has.
    renderInShell(<CheckinQrSection />);
    const url = await screen.findByText(CHECKIN_URL);
    expect(url.tagName).toBe("BDI");
    // A Latin URL inside a Hebrew page: without dir="ltr" the trailing "/checkin"
    // reorders around the neutral characters and the printed address is wrong.
    expect(url).toHaveAttribute("dir", "ltr");
  });

  it("renders the server's SVG through a data: URI, unchanged", async () => {
    // The whole encode, not just the prefix: a double-encoded or truncated
    // payload is a square that draws nothing, and the suite would otherwise be
    // satisfied by a src that merely starts with the right ten characters.
    renderInShell(<CheckinQrSection />);
    const image = await screen.findByRole("img");
    const src = image.getAttribute("src") ?? "";
    expect(src.startsWith(DATA_PREFIX)).toBe(true);
    expect(decodeURIComponent(src.slice(DATA_PREFIX.length))).toBe(SVG);
  });

  it("gives the code a real alt that does not repeat the URL", async () => {
    renderInShell(<CheckinQrSection />);
    const image = await screen.findByRole("img");
    const alt = image.getAttribute("alt") ?? "";
    expect(alt.length).toBeGreaterThan(0);
    // The URL is already adjacent text. An alt that repeats it makes a screen
    // reader read the address twice and says nothing about what the code IS.
    expect(alt).not.toContain(CHECKIN_URL);
  });

  it("prints the sheet rather than navigating away", async () => {
    // The affordance is window.print() and a print stylesheet, so this is the
    // only thing that can assert the button is wired at all.
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    renderInShell(<CheckinQrSection />);
    fireEvent.click(await screen.findByRole("button", { name: "הדפסה" }));
    expect(print).toHaveBeenCalledTimes(1);
    print.mockRestore();
  });

  it("keeps the printed sheet marked so the console chrome can be hidden", async () => {
    // The print isolation lives in index.css and keys off this class; jsdom
    // applies no stylesheet, so the class is the only half of the mechanism a
    // unit test can see. Losing it prints the nav and the header onto the door.
    renderInShell(<CheckinQrSection />);
    const image = await screen.findByRole("img");
    expect(image.closest(".print-sheet")).not.toBeNull();
  });

  it("renders an alert and no code when the read fails", async () => {
    getCheckinQr.mockRejectedValue(new Error("offline"));
    renderInShell(<CheckinQrSection />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הצלחנו לטעון את קוד הסריקה כרגע.",
    );
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("passes axe with zero violations on the loaded code", async () => {
    const { container } = renderInShell(<CheckinQrSection />);
    await screen.findByRole("img");
    const results = await run(container);
    expect(results.violations).toEqual([]);
  });

  it("passes axe with zero violations on the failed read", async () => {
    getCheckinQr.mockRejectedValue(new Error("offline"));
    const { container } = renderInShell(<CheckinQrSection />);
    await screen.findByRole("alert");
    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
