import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { JoinPanel } from "../components/JoinPanel";
import { extractCode } from "../validation";
import "../i18n";

const fetchMock = vi.fn();

function json(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function refusal(code: string, status: number): Response {
  return json(status, { error: { code, message: "English the screen must never show." } });
}

const INVITE = { slug: "bella", name: "בלה כלות", owner_email: "dana@bella.example" };

// The FRAGMENT, matching the link the server now builds: `#code=` is never sent
// to any server, so the credential reaches no access log.
function atPath(fragment: string) {
  window.history.replaceState({}, "", `/platform/join${fragment}`);
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  atPath("");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("extractCode", () => {
  it("accepts a pasted full link, a bare code, and whitespace around either", () => {
    // Design B1. The owner was GIVEN a link, so a link is what she pastes, and
    // refusing it would spend a failures-only limiter attempt on a formatting
    // mistake — three of those lock her out for fifteen minutes.
    // The shipped link is a FRAGMENT link — that is the shape she actually holds.
    expect(extractCode("https://admin.modryn.co.il/platform/join#code=abc123")).toBe("abc123");
    expect(extractCode("  https://admin.modryn.co.il/platform/join#code=abc123  ")).toBe("abc123");
    // A query-shaped one still works: an older link, or a mail client that
    // rewrote it, must not cost her a limiter attempt.
    expect(extractCode("https://admin.modryn.co.il/platform/join?code=abc123")).toBe("abc123");
    expect(extractCode("https://admin.modryn.co.il/platform/join?code=abc123&x=1")).toBe("abc123");
    expect(extractCode("abc123")).toBe("abc123");
    expect(extractCode("  abc123 ")).toBe("abc123");
  });
});

describe("the join panel", () => {
  it("starts on the code step and calls nothing when the URL carries no code", async () => {
    render(<JoinPanel />);
    expect(
      await screen.findByRole("heading", { name: "הזנת קוד הזמנה", level: 2 }),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders the three facts READ-ONLY, with no editable slug or email anywhere", async () => {
    // ⚠ THE ASSERTION THAT CARRIES D2. The redeemer's form has exactly ONE
    // input — her password. A slug or email box here would make a leaked link a
    // bearer token for "become the owner of a boutique of my choosing".
    atPath("#code=abc123");
    fetchMock.mockResolvedValue(json(200, INVITE));
    render(<JoinPanel />);

    await screen.findByRole("heading", { name: "הקמת הבוטיק", level: 2 });
    expect(screen.getByText("בלה כלות")).toBeInTheDocument();
    expect(screen.getByText("bella.modryn.co.il")).toBeInTheDocument();
    expect(screen.getByText("dana@bella.example")).toBeInTheDocument();

    // EVERY <input> on the screen, not just the ones with a queryable role — a
    // password box has no implicit ARIA role, so a role-based query alone would
    // have counted zero and passed vacuously.
    const inputs = Array.from(document.querySelectorAll("input"));
    expect(inputs).toHaveLength(1);
    expect(inputs[0]).toHaveAttribute("type", "password");
    expect(inputs[0]).toHaveAttribute("minlength", "10");
    expect(inputs[0]).toHaveAttribute("autocomplete", "new-password");
    expect(inputs[0]).toHaveAttribute("required");
  });

  it("shows ONE sentence for every invalid state and never the server's English", async () => {
    // D5 anti-enumeration: unknown / expired / redeemed / revoked are one 404
    // with one code, and the UI must not undo that by distinguishing them.
    atPath("#code=nope");
    fetchMock.mockResolvedValue(refusal("invalid_invite", 404));
    render(<JoinPanel />);

    expect(
      await screen.findByText("ההזמנה אינה תקפה. אפשר לבקש מ‑MODRYN הזמנה חדשה."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "הזנת קוד הזמנה", level: 2 })).toBeInTheDocument();
    expect(screen.queryByText("English the screen must never show.")).not.toBeInTheDocument();
  });

  it("puts a weak-password refusal in the FIELD's error slot, not the form alert", async () => {
    atPath("#code=abc123");
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url.startsWith("/platform/join/invite")
          ? json(200, INVITE)
          : refusal("password_too_short", 400),
      ),
    );
    render(<JoinPanel />);
    await screen.findByRole("heading", { name: "הקמת הבוטיק", level: 2 });

    const password = screen.getByLabelText("בחירת סיסמה");
    await userEvent.type(password, "short");
    await userEvent.click(screen.getByRole("button", { name: "הקמת הבוטיק" }));

    // ⚠ `findByRole("alert")` and NOT a text query: the SAME sentence is already
    // on screen as the field's `help`, shown before submit so the failure is
    // prevented rather than reported. A text query would match both and could not
    // tell the prevention from the report.
    const message = await screen.findByRole("alert");
    expect(message).toHaveTextContent("הסיסמה חייבת להכיל לפחות 10 תווים.");
    // Wired to the control, which is the whole point of the field slot: a screen
    // reader user must be able to tell WHICH box is wrong.
    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(password.getAttribute("aria-describedby")).toContain(message.id);
    // …and the form is still usable — this refusal is a retry, not an ending.
    expect(screen.getByRole("button", { name: "הקמת הבוטיק" })).not.toBeDisabled();
  });

  it("clears the password and disables the form on a RACED invalid_invite", async () => {
    // Revoked or redeemed between the preview and the submit. There is nothing
    // left to retry, and leaving a live password in a dead form invites her to
    // keep pressing.
    atPath("#code=abc123");
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url.startsWith("/platform/join/invite") ? json(200, INVITE) : refusal("invalid_invite", 404),
      ),
    );
    render(<JoinPanel />);
    await screen.findByRole("heading", { name: "הקמת הבוטיק", level: 2 });

    const password = screen.getByLabelText("בחירת סיסמה");
    await userEvent.type(password, "a-long-enough-password");
    await userEvent.click(screen.getByRole("button", { name: "הקמת הבוטיק" }));

    await waitFor(() => {
      expect(
        screen.getByText("ההזמנה אינה תקפה. אפשר לבקש מ‑MODRYN הזמנה חדשה."),
      ).toBeInTheDocument();
    });
    expect(password).toHaveValue("");
    expect(password).toBeDisabled();
    expect(screen.getByRole("button", { name: "הקמת הבוטיק" })).toBeDisabled();
  });

  it("shows the rate-limited sentence on a 429, keyed on status", async () => {
    atPath("#code=abc123");
    fetchMock.mockResolvedValue(refusal("TOO_MANY_ATTEMPTS", 429));
    render(<JoinPanel />);
    expect(
      await screen.findByText("יותר מדי ניסיונות. אפשר לנסות שוב בעוד מספר דקות."),
    ).toBeInTheDocument();
  });

  it("reaches the success screen with the manage link and never repeats the password", async () => {
    atPath("#code=abc123");
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        url.startsWith("/platform/join/invite")
          ? json(200, INVITE)
          : json(200, { slug: "bella", manage_url: "https://bella.modryn.co.il/manage" }),
      ),
    );
    render(<JoinPanel />);
    await screen.findByRole("heading", { name: "הקמת הבוטיק", level: 2 });

    const secret = "a-long-enough-password";
    await userEvent.type(screen.getByLabelText("בחירת סיסמה"), secret);
    await userEvent.click(screen.getByRole("button", { name: "הקמת הבוטיק" }));

    await screen.findByRole("heading", { name: "הבוטיק מוכן", level: 2 });
    const link = screen.getByRole("link", { name: "כניסה לניהול הבוטיק" });
    expect(link).toHaveAttribute("href", "https://bella.modryn.co.il/manage");
    expect(document.body.textContent).not.toContain(secret);
    // D7: no payment copy on a screen in a feature that ships no payment code.
    expect(document.body.textContent).not.toMatch(/תשלום|מקדמה|סליקה/);
  });

  it("passes no size to any control — 44px is the floor (F-W1)", async () => {
    atPath("#code=abc123");
    fetchMock.mockResolvedValue(json(200, INVITE));
    const { container } = render(<JoinPanel />);
    await screen.findByRole("heading", { name: "הקמת הבוטיק", level: 2 });
    // `sm` is min-h-9 = 36px. The class is what a passed size would leave behind.
    expect(container.querySelectorAll(".min-h-9")).toHaveLength(0);
  });
});
