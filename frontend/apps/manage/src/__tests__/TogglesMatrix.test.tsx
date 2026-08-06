import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Settings } from "../api";
// Side-effect import: the card renders through useTranslation, so without
// i18next initialised every assertion below would match a bare key.
import "../i18n";
import { TogglesMatrix } from "../components/TogglesMatrix";
import { TOGGLE_AREAS, TOGGLES } from "../lib/toggles";

const toast = vi.fn();

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { updateSettings: vi.fn() },
  };
});

vi.mock("@boutique/ui", async () => {
  const actual = await vi.importActual<typeof import("@boutique/ui")>("@boutique/ui");
  return { ...actual, useToast: () => toast };
});

const { api } = await import("../api");
const updateSettings = vi.mocked(api.updateSettings);

// The wire is DEFAULT-COMPLETE (D3), so a fixture that omitted a key would not
// be testing what the parent actually hands this card.
function wire(overrides: Record<string, boolean> = {}): Record<string, boolean> {
  return Object.fromEntries(TOGGLES.map(({ key }) => [key, overrides[key] ?? false]));
}

function settings(toggles: Record<string, boolean> = wire()): Settings {
  return { profile: {}, toggles };
}

function renderMatrix(toggles: Record<string, boolean> = wire()) {
  return render(<TogglesMatrix toggles={toggles} />);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TogglesMatrix rows come from the registry", () => {
  it("renders exactly one switch per registry key, with its label", () => {
    // ⚠ EXACTLY, not "at least". The count is the D1 drift tripwire: a key added
    // to the backend registry and forgotten here, or vice versa, is an extra or
    // missing row rather than a silent divergence.
    renderMatrix();
    const switches = screen.getAllByRole("switch");
    expect(switches).toHaveLength(TOGGLES.length);
    for (const { key } of TOGGLES) {
      expect(screen.getByRole("switch", { name: new RegExp(labelOf(key)) })).toBeInTheDocument();
    }
  });

  it("groups the rows under an area heading each, in registry order", () => {
    // Design P2: the grouped skeleton ships at two rows because it is the D8
    // contract future rows land into — F23's waitlist joins `booking`, F46 opens
    // a messages area, and neither PR touches layout.
    renderMatrix();
    const headings = screen.getAllByRole("heading", { level: 3 }).map((node) => node.textContent);
    expect(headings).toEqual(TOGGLE_AREAS.map((area) => areaLabel(area)));
  });

  it("reflects the wire's values rather than defaulting everything off", () => {
    renderMatrix(wire({ brides_only: true }));
    expect(switchFor("brides_only")).toBeChecked();
    expect(switchFor("deposits_enabled")).not.toBeChecked();
  });

  it("renders each row's hint as the switch's description", () => {
    renderMatrix();
    // §3: the hint IS the flip-consequence line, and it must be wired to the
    // input (aria-describedby), not merely printed nearby.
    const described = switchFor("deposits_enabled").getAttribute("aria-describedby");
    expect(described).toBeTruthy();
    expect(document.getElementById(described as string)?.textContent).toContain(
      "אחרי שחשבון הסליקה",
    );
  });
});

describe("TogglesMatrix per-row save", () => {
  it("PUTs EXACTLY ONE key — never the whole block", async () => {
    // The single-key patch is the whole point of D2's deep merge. Sending the
    // sibling too would work today and would silently re-create the stale-bundle
    // clobber the moment the registry grows.
    updateSettings.mockResolvedValue(settings(wire({ brides_only: true })));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(1));
    expect(updateSettings).toHaveBeenCalledWith({ toggles: { brides_only: true } });
  });

  it("re-syncs the row from the RESPONSE, not from the optimistic value", async () => {
    // FloorPanel's no-optimistic-patch discipline: the server is the truth, so a
    // save the server answers differently must land on the server's answer.
    updateSettings.mockResolvedValue(settings(wire({ brides_only: false })));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));

    await waitFor(() => expect(updateSettings).toHaveBeenCalled());
    await waitFor(() => expect(switchFor("brides_only")).not.toBeChecked());
  });

  it("shows the saved cue in ONE status region and announces it there", async () => {
    updateSettings.mockResolvedValue(settings(wire({ brides_only: true })));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));

    // One region per CARD (FloorPanel's one-cue precedent), not one per row.
    const regions = screen.getAllByRole("status");
    expect(regions).toHaveLength(1);
    await waitFor(() => expect(regions[0]).toHaveTextContent("נשמר לפני רגע"));
  });

  it("clears the saved cue on the next flip anywhere in the card", async () => {
    updateSettings.mockResolvedValue(settings(wire({ brides_only: true })));
    renderMatrix();
    fireEvent.click(switchFor("brides_only"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("נשמר לפני רגע"));

    updateSettings.mockReturnValue(new Promise(() => {}));
    fireEvent.click(switchFor("deposits_enabled"));

    expect(screen.getByRole("status")).toHaveTextContent("");
  });
});

describe("TogglesMatrix in-flight lock", () => {
  it("ignores a second flip while that row's PUT is pending", async () => {
    updateSettings.mockReturnValue(new Promise(() => {}));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));
    fireEvent.click(switchFor("brides_only"));
    fireEvent.click(switchFor("brides_only"));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(1));
  });

  it("NEVER sets the disabled attribute on a switch — design P1", () => {
    // ⚠ THE LOCK IS A HANDLER GUARD, NOT `disabled`. Disabling a just-flipped
    // (therefore focused) native checkbox drops focus to <body> — an SC 2.4.3
    // regression. jsdom cannot prove where focus LANDS in a real browser (that
    // is e2e's job), but it can prove the attribute that would cause it is never
    // set, which is the mechanism.
    updateSettings.mockReturnValue(new Promise(() => {}));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));

    for (const node of screen.getAllByRole("switch")) {
      expect(node).not.toBeDisabled();
    }
  });

  it("locks only the row in flight — the sibling row stays live", async () => {
    updateSettings.mockReturnValue(new Promise(() => {}));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));
    fireEvent.click(switchFor("deposits_enabled"));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(2));
    expect(updateSettings).toHaveBeenNthCalledWith(2, { toggles: { deposits_enabled: true } });
  });
});

describe("TogglesMatrix failure", () => {
  it("reverts the switch to its pre-flip state and raises the house toast", async () => {
    updateSettings.mockRejectedValue(new Error("network down"));
    renderMatrix(wire({ brides_only: true }));

    fireEvent.click(switchFor("brides_only"));

    await waitFor(() => expect(toast).toHaveBeenCalledTimes(1));
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ variant: "error" }));
    // Back to ON — the value it had before the failed flip.
    expect(switchFor("brides_only")).toBeChecked();
  });

  it("renders no inline row error — the toast is the whole error surface", async () => {
    updateSettings.mockRejectedValue(new Error("network down"));
    renderMatrix();

    fireEvent.click(switchFor("brides_only"));

    await waitFor(() => expect(toast).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("TogglesMatrix has no dialog and no gateway warning", () => {
  it("renders no confirm dialog on any flip (design §8)", async () => {
    // Every shipped row's flip is reversible and touches nothing in flight, so a
    // confirm would be ceremony. A future dangerous row argues for its own.
    updateSettings.mockResolvedValue(settings(wire({ deposits_enabled: true })));
    renderMatrix();

    fireEvent.click(switchFor("deposits_enabled"));

    await waitFor(() => expect(updateSettings).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("adds NO banner when deposits go on with no gateway connected (F-T3)", async () => {
    // Turning deposits on before connecting a gateway is legal and useful — the
    // owner prepares. The hint plus the shipped `gateway.depositsWithoutGateway`
    // banner already cover it; a second warning here would be nagging.
    updateSettings.mockResolvedValue(settings(wire({ deposits_enabled: true })));
    const { container } = renderMatrix();

    fireEvent.click(switchFor("deposits_enabled"));
    await waitFor(() => expect(updateSettings).toHaveBeenCalled());

    expect(within(container).queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/סליקה/)).toBeInTheDocument(); // only the hint's own sentence
    expect(screen.getAllByText(/סליקה/)).toHaveLength(1);
  });
});

// --- helpers -----------------------------------------------------------------

function labelOf(key: string): string {
  const labels: Record<string, string> = {
    brides_only: "בוטיק לכלות בלבד",
    deposits_enabled: "גביית מקדמות מופעלת",
  };
  return labels[key] ?? key;
}

function areaLabel(area: string): string {
  const labels: Record<string, string> = {
    storefront: "האתר הפומבי",
    booking: "תורים ותשלומים",
  };
  return labels[area] ?? area;
}

function switchFor(key: string): HTMLElement {
  return screen.getByRole("switch", { name: new RegExp(labelOf(key)) });
}
