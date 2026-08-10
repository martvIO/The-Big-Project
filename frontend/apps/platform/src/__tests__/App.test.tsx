import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
const BELLA = {
  slug: "bella",
  name: "בלה כלות",
  status: "active",
  created_at: "2026-08-01T09:30:00Z",
};

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
        url === "/platform/auth/me" ? json(200, OPERATOR) : json(200, { tenants: [], invites: [] }),
      ),
    );
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "ניהול הפלטפורמה", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Dana")).toBeInTheDocument();
  });

  it("flips back to login with the calm expiry line on a mid-session 401", async () => {
    // ⚠ DRIVEN THROUGH A REAL CONSOLE ACTION, not a synthetic event. The 4h TTL
    // is fixed and nothing slides it, so a working console WILL expire under an
    // operator mid-task — and suspend is one of the three actions she is most
    // likely to be halfway through when it does. Console.tsx catches its own
    // ApiError to render a refusal sentence, so a hand-dispatched
    // `unhandledrejection` proved only that the listener worked, never that any
    // real path reached it. None did.
    fetchMock.mockImplementation((url: string) => {
      if (url === "/platform/auth/me") return Promise.resolve(json(200, OPERATOR));
      if (url === "/platform/tenants") return Promise.resolve(json(200, { tenants: [BELLA] }));
      // F26's second mount fetch. Left at 401 it would expire the session before
      // the operator ever reached the action this test is about.
      if (url === "/platform/invites") return Promise.resolve(json(200, { invites: [] }));
      return Promise.resolve(
        json(401, { error: { code: "NOT_AUTHENTICATED", message: "Authentication required." } }),
      );
    });
    render(<App />);
    await screen.findByRole("heading", { name: "ניהול הפלטפורמה", level: 1 });

    const row = (await screen.findByText("בלה כלות")).closest("tr") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: "השהיה" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "השהיה" }));

    await waitFor(() => {
      expect(screen.getByText("ההתחברות הסתיימה. יש להיכנס שוב.")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "כניסה" })).toBeInTheDocument();
    // The backend's English must never reach the screen: the whole point of the
    // flip is that she gets the Hebrew login panel instead of a raw refusal.
    expect(screen.queryByText("Authentication required.")).not.toBeInTheDocument();
  });

  it("leaves a REFUSED LOGIN on the login screen's own copy", async () => {
    // The guard on the subscription. A 401 from `login` is a wrong password, not
    // an expiry, and answering it with «ההתחברות הסתיימה» would tell an operator
    // her session died when she never had one.
    fetchMock.mockResolvedValue(
      json(401, { error: { code: "INVALID_CREDENTIALS", message: "Invalid credentials." } }),
    );
    render(<App />);
    await userEvent.type(await screen.findByLabelText("אימייל"), "dana@modryn.example");
    await userEvent.type(screen.getByLabelText("סיסמה"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "כניסה" }));

    expect(await screen.findByText("האימייל או הסיסמה אינם נכונים.")).toBeInTheDocument();
    expect(screen.queryByText("ההתחברות הסתיימה. יש להיכנס שוב.")).not.toBeInTheDocument();
  });
});

describe("the join branch", () => {
  // F26 D1. The console's bootstrap and the redeemer's screen live in ONE
  // bundle at two exact paths; the branch is what keeps them from touching.
  afterEach(() => {
    window.history.replaceState({}, "", "/platform");
  });

  it("renders the join panel on /platform/join and NEVER calls me()", async () => {
    // ⚠ THE ASSERTION THAT MATTERS IS THE ABSENCE. `me()` for a redeemer is a
    // guaranteed 401 — one pointless round trip on the one screen in this app a
    // non-operator opens, and a 401 that would arm the session-expired listener
    // for somebody who never had a session.
    window.history.replaceState({}, "", "/platform/join");
    fetchMock.mockResolvedValue(json(200, { tenants: [] }));
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "הזנת קוד הזמנה", level: 2 }),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "כניסה" })).not.toBeInTheDocument();
  });

  it("still bootstraps normally on /platform", async () => {
    window.history.replaceState({}, "", "/platform");
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url === "/platform/auth/me" ? json(200, OPERATOR) : json(200, { tenants: [], invites: [] }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "ניהול הפלטפורמה", level: 1 });
    expect(fetchMock).toHaveBeenCalledWith("/platform/auth/me", expect.anything());
  });
});
