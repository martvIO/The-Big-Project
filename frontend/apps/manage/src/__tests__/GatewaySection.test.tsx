import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { run } from "axe-core";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { GatewayStatus, Settings } from "../api";
import { GatewaySection } from "../components/GatewaySection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      gatewayStatus: vi.fn(),
      getSettings: vi.fn(),
      setGatewayCredentials: vi.fn(),
      validateGateway: vi.fn(),
      disconnectGateway: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const gatewayStatus = vi.mocked(api.gatewayStatus);
const getSettings = vi.mocked(api.getSettings);
const setGatewayCredentials = vi.mocked(api.setGatewayCredentials);
const validateGateway = vi.mocked(api.validateGateway);
const disconnectGateway = vi.mocked(api.disconnectGateway);

const FIELDS = ["api_key", "merchant_id", "webhook_secret"];

function status(overrides: Partial<GatewayStatus> = {}): GatewayStatus {
  return {
    provider: "fake",
    configured: true,
    connected: true,
    status: "valid",
    last_validated_at: "2026-07-31T09:12:00Z",
    credential_fields: FIELDS,
    ...overrides,
  };
}

function settings(depositsEnabled: boolean): Settings {
  return { profile: {}, toggles: { deposits_enabled: depositsEnabled, brides_only: false } };
}

// GatewaySection renders inside ConsoleShell's <main>, which owns the console's
// single sr-only <h1>. The axe harness reproduces that frame rather than
// scanning a headless fragment (the StaffSection precedent).
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
  gatewayStatus.mockResolvedValue(status());
  getSettings.mockResolvedValue(settings(false));
  setGatewayCredentials.mockResolvedValue(status());
  validateGateway.mockResolvedValue(status());
  disconnectGateway.mockResolvedValue(status({ connected: false, status: null }));
});

// --- the three status renderings ---

describe("the three status renderings", () => {
  it("shows an explanatory line and NO form when the platform has no gateway", async () => {
    gatewayStatus.mockResolvedValue(
      status({ provider: null, configured: false, connected: false, status: null,
        last_validated_at: null, credential_fields: [] }),
    );
    renderInShell(<GatewaySection />);
    expect(await screen.findByText("גביית מקדמות אינה זמינה כרגע בפלטפורמה.")).toBeTruthy();
    // Nothing here is the owner's to fix, so offering her a form would be a lie.
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByLabelText("מפתח API")).toBeNull();
  });

  it("shows the form and no badge when the platform is configured but nothing is connected", async () => {
    gatewayStatus.mockResolvedValue(
      status({ connected: false, status: null, last_validated_at: null }),
    );
    renderInShell(<GatewaySection />);
    expect(await screen.findByText("עדיין לא חובר חשבון סליקה.")).toBeTruthy();
    expect(screen.getByLabelText("מפתח API")).toBeTruthy();
    // No live account, so nothing to validate or disconnect.
    expect(screen.queryByRole("button", { name: "בדיקה עכשיו" })).toBeNull();
    expect(screen.queryByRole("button", { name: "ניתוק חשבון הסליקה" })).toBeNull();
  });

  it("shows the connected badge and the last-validated instant", async () => {
    renderInShell(<GatewaySection />);
    expect(await screen.findByText("חשבון הסליקה מחובר.")).toBeTruthy();
    expect(screen.getByText("פעיל")).toBeTruthy();
    expect(screen.getByText("נבדק לאחרונה", { exact: false })).toBeTruthy();
  });

  it("renders the invalid badge for a refused credential set", async () => {
    gatewayStatus.mockResolvedValue(status({ connected: false, status: "invalid" }));
    renderInShell(<GatewaySection />);
    expect(await screen.findByText("נדחה")).toBeTruthy();
  });
});

// --- the write-only form ---

describe("the credentials form", () => {
  it("is empty on load and sends the COMPLETE set on submit", async () => {
    renderInShell(<GatewaySection />);
    const apiKey = (await screen.findByLabelText("מפתח API")) as HTMLInputElement;
    // Write-only by construction: the API has no read path for a field value,
    // so there is nothing to prefill.
    expect(apiKey.value).toBe("");
    expect(apiKey.type).toBe("password");
    expect(apiKey.autocomplete).toBe("off");

    fireEvent.change(apiKey, { target: { value: "k-1" } });
    fireEvent.change(screen.getByLabelText("מזהה סוחר"), { target: { value: "m-1" } });
    fireEvent.change(screen.getByLabelText("סוד אימות התראות"), { target: { value: "s-1" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת פרטי הסליקה" }));

    await waitFor(() => expect(setGatewayCredentials).toHaveBeenCalledTimes(1));
    expect(setGatewayCredentials).toHaveBeenCalledWith({
      api_key: "k-1",
      merchant_id: "m-1",
      webhook_secret: "s-1",
    });
  });

  it("re-empties the form after a successful save", async () => {
    renderInShell(<GatewaySection />);
    const apiKey = (await screen.findByLabelText("מפתח API")) as HTMLInputElement;
    fireEvent.change(apiKey, { target: { value: "k-1" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת פרטי הסליקה" }));
    await waitFor(() => expect((screen.getByLabelText("מפתח API") as HTMLInputElement).value).toBe(""));
  });

  it("renders the section's own Hebrew for a refused credential set, never a provider message", async () => {
    setGatewayCredentials.mockRejectedValue(
      new ApiError(400, "GATEWAY_CREDENTIALS_REJECTED", "The payment account details were refused."),
    );
    renderInShell(<GatewaySection />);
    await screen.findByLabelText("מפתח API");
    fireEvent.click(screen.getByRole("button", { name: "שמירת פרטי הסליקה" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("פרטי הסליקה נדחו");
    // The server's body is English and errorMessage() would surface it verbatim.
    expect(alert.textContent).not.toContain("refused");
  });

  it("falls back to the server's own message for an unmapped code", async () => {
    setGatewayCredentials.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "missing credential fields: webhook_secret"),
    );
    renderInShell(<GatewaySection />);
    await screen.findByLabelText("מפתח API");
    fireEvent.click(screen.getByRole("button", { name: "שמירת פרטי הסליקה" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("missing credential fields: webhook_secret");
  });
});

// --- the unkeyed-field fallback (Risk 9) ---

describe("an unkeyed credential field", () => {
  it("renders its RAW name inside <bdi dir=ltr lang=en>", async () => {
    // The day a real-provider adapter declares its own field set, the form
    // follows with no frontend edit — that is the design working — and any
    // Hebrew label keyed to a fake field name becomes dead. The raw name is an
    // LTR snake_case run inside RTL Hebrew, so it needs BOTH the bidi isolation
    // and the WCAG 3.1.2 language mark. An axe pass cannot catch a missing one,
    // because a <label> element exists either way — which is why this assertion
    // lives here and not in i18n.test.ts, a suite that cannot see a key it never
    // renders.
    gatewayStatus.mockResolvedValue(status({ credential_fields: ["store_id"] }));
    const { container } = renderInShell(<GatewaySection />);
    await screen.findByLabelText("store_id");
    const bdi = container.querySelector("bdi[lang='en']");
    expect(bdi).not.toBeNull();
    expect(bdi?.getAttribute("dir")).toBe("ltr");
    expect(bdi?.textContent).toBe("store_id");
  });

  it("still uses the Hebrew label for a keyed field", async () => {
    gatewayStatus.mockResolvedValue(status({ credential_fields: ["api_key", "store_id"] }));
    const { container } = renderInShell(<GatewaySection />);
    expect(await screen.findByLabelText("מפתח API")).toBeTruthy();
    // Exactly one falls back — the keyed one must not be wrapped.
    expect(container.querySelectorAll("bdi[lang='en']").length).toBe(1);
  });
});

// --- the test-environment notice ---

describe("the test-environment notice", () => {
  it("is present when the provider is the fake one", async () => {
    renderInShell(<GatewaySection />);
    // Staging runs the fake secret box: both production boot guards key on
    // APP_ENV=production and 0012's CHECK admits 'fake' everywhere, so a real
    // merchant credential typed here WOULD be stored as base64 of plaintext.
    expect(
      await screen.findByText("סביבת בדיקות — אין להזין פרטי סליקה אמיתיים"),
    ).toBeTruthy();
  });

  it("is absent for any other provider", async () => {
    gatewayStatus.mockResolvedValue(status({ provider: "lemonsqueezy" }));
    renderInShell(<GatewaySection />);
    await screen.findByLabelText("מפתח API");
    expect(screen.queryByText("סביבת בדיקות — אין להזין פרטי סליקה אמיתיים")).toBeNull();
  });
});

// --- validate and the two-step disconnect ---

describe("validate and disconnect", () => {
  it("re-pings on «בדיקה עכשיו» and re-renders the badge", async () => {
    validateGateway.mockResolvedValue(status({ connected: false, status: "invalid" }));
    renderInShell(<GatewaySection />);
    fireEvent.click(await screen.findByRole("button", { name: "בדיקה עכשיו" }));
    await waitFor(() => expect(validateGateway).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("נדחה")).toBeTruthy();
  });

  it("needs two taps to disconnect — the F16 cancel precedent", async () => {
    renderInShell(<GatewaySection />);
    fireEvent.click(await screen.findByRole("button", { name: "ניתוק חשבון הסליקה" }));
    // First tap REVEALS, it does not act: disconnecting stops deposits for the
    // whole boutique.
    expect(disconnectGateway).not.toHaveBeenCalled();
    expect(screen.getByText("לנתק את חשבון הסליקה?", { exact: false })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "ניתוק" }));
    await waitFor(() => expect(disconnectGateway).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("עדיין לא חובר חשבון סליקה.")).toBeTruthy();
  });

  it("cancels the reveal without calling the API", async () => {
    renderInShell(<GatewaySection />);
    fireEvent.click(await screen.findByRole("button", { name: "ניתוק חשבון הסליקה" }));
    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    expect(disconnectGateway).not.toHaveBeenCalled();
    expect(screen.queryByText("לנתק את חשבון הסליקה?", { exact: false })).toBeNull();
  });
});

// --- the cross-section banner ---

describe("the deposits-on-with-no-gateway banner", () => {
  it("appears when deposits are enabled and nothing is connected", async () => {
    gatewayStatus.mockResolvedValue(status({ connected: false, status: null }));
    getSettings.mockResolvedValue(settings(true));
    renderInShell(<GatewaySection />);
    expect(
      await screen.findByText("גביית מקדמות מופעלת בהגדרות, אבל אין חשבון סליקה מחובר."),
    ).toBeTruthy();
  });

  it("is absent when a gateway IS connected", async () => {
    getSettings.mockResolvedValue(settings(true));
    renderInShell(<GatewaySection />);
    await screen.findByText("חשבון הסליקה מחובר.");
    expect(
      screen.queryByText("גביית מקדמות מופעלת בהגדרות, אבל אין חשבון סליקה מחובר."),
    ).toBeNull();
  });

  it("is absent when deposits are off, however disconnected the gateway is", async () => {
    gatewayStatus.mockResolvedValue(status({ connected: false, status: null }));
    getSettings.mockResolvedValue(settings(false));
    renderInShell(<GatewaySection />);
    await screen.findByText("עדיין לא חובר חשבון סליקה.");
    expect(
      screen.queryByText("גביית מקדמות מופעלת בהגדרות, אבל אין חשבון סליקה מחובר."),
    ).toBeNull();
  });
});

// --- containment + a11y ---

describe("containment and accessibility", () => {
  it("never renders a typed credential back into the document after a save", async () => {
    renderInShell(<GatewaySection />);
    const apiKey = await screen.findByLabelText("מפתח API");
    fireEvent.change(apiKey, { target: { value: "SUPER-SECRET-MERCHANT-KEY-8f3a" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת פרטי הסליקה" }));
    await waitFor(() => expect(setGatewayCredentials).toHaveBeenCalled());
    await waitFor(() =>
      expect(document.body.innerHTML).not.toContain("SUPER-SECRET-MERCHANT-KEY-8f3a"),
    );
  });

  it("passes axe in the connected state", async () => {
    const { container } = renderInShell(<GatewaySection />);
    await screen.findByLabelText("מפתח API");
    const results = await run(container);
    expect(results.violations).toEqual([]);
  });

  it("passes axe in the unconfigured state", async () => {
    gatewayStatus.mockResolvedValue(
      status({ provider: null, configured: false, connected: false, status: null,
        last_validated_at: null, credential_fields: [] }),
    );
    const { container } = renderInShell(<GatewaySection />);
    await screen.findByText("גביית מקדמות אינה זמינה כרגע בפלטפורמה.");
    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
