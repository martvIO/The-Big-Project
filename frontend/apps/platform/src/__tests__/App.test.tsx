import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import "../i18n";

const fetchMock = vi.fn();

function json(status: number, body: unknown): Response {
  return {
    ok: status < 400,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const OPERATOR = { email: "dana@modryn.example", display_name: "Dana" };

describe("the console bootstrap", () => {
  it("renders the login panel when /platform/auth/me is 401", async () => {
    fetchMock.mockResolvedValue(
      json(401, { error: { code: "NOT_AUTHENTICATED", message: "Authentication required." } }),
    );
    render(<App />);
    expect(await screen.findByRole("button", { name: "כניסה" })).toBeInTheDocument();
    // The console's own heading must NOT be on the page — a shell that renders
    // behind a login form is how an operator sees data she is not signed in for.
    expect(screen.queryByRole("heading", { name: "ניהול הפלטפורמה" })).not.toBeInTheDocument();
  });

  it("renders the console when /platform/auth/me is 200", async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url === "/platform/auth/me" ? json(200, OPERATOR) : json(200, { tenants: [] }),
      ),
    );
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "ניהול הפלטפורמה", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Dana")).toBeInTheDocument();
  });

  it("flips back to login with the calm expiry line on a mid-session 401", async () => {
    // The 4h TTL is FIXED and nothing slides it, so a working console will
    // expire under an operator mid-task. `role="status"`, not `alert`: nothing
    // went wrong.
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url === "/platform/auth/me" ? json(200, OPERATOR) : json(200, { tenants: [] }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "ניהול הפלטפורמה", level: 1 });

    const { ApiError } = await import("../api");
    window.dispatchEvent(
      Object.assign(new Event("unhandledrejection"), {
        reason: new ApiError(401, "NOT_AUTHENTICATED", "Authentication required."),
      }),
    );

    await waitFor(() => {
      expect(screen.getByText("ההתחברות הסתיימה. יש להיכנס שוב.")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "כניסה" })).toBeInTheDocument();
  });
});
