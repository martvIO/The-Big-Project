import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api";
import type { StaffNotification } from "../api";
import { NotificationBell } from "../components/NotificationBell";
import { SosContext, type SosContextValue } from "../lib/sos-context";
import i18n from "../i18n";

/**
 * F35's control and panel.
 *
 * ⚠ **ASSERT CONTENT, NEVER FOCUS.** jsdom has no `<dialog>` and `setup.ts`
 * stubs `showModal()`, so a focus assertion that pre-places focus on its own
 * target is vacuous. Real focus behaviour — the trap, Esc, the return to the
 * bell and the move to `#console-main` — is the e2e leg's job.
 *
 * ⚠ **The provider is faked here rather than mounted.** `SosProvider` owns a
 * poll; this file is about a control that owns none, and mounting the real one
 * would put a timer into every test in it.
 */

const NOW = "2026-08-06T11:32:00Z";

function row(overrides: Partial<StaffNotification> = {}): StaffNotification {
  return {
    id: crypto.randomUUID(),
    kind: "dispatch_assigned",
    actor_name: "דנה כהן",
    created_at: NOW,
    read_at: null,
    ...overrides,
  };
}

function mount(options: { unread?: number; markRead?: SosContextValue["markRead"] } = {}) {
  const value = {
    alerts: [],
    serverNow: NOW,
    unreadNotifications: options.unread ?? 0,
    markRead: options.markRead ?? vi.fn().mockResolvedValue(null),
    terminal: null,
    channelDown: false,
    raise: vi.fn(),
    accept: vi.fn(),
    resolve: vi.fn(),
    cancel: vi.fn(),
  } as unknown as SosContextValue;
  const onOpenFloor = vi.fn();
  const view = render(
    <SosContext.Provider value={value}>
      <div id="console-main" tabIndex={-1} />
      <NotificationBell onOpenFloor={onOpenFloor} />
    </SosContext.Provider>,
  );
  return { ...view, onOpenFloor, value };
}

function bell() {
  return screen.getByRole("button", { name: /התראות/ });
}

async function openPanel() {
  await act(async () => {
    fireEvent.click(bell());
  });
}

beforeEach(() => {
  vi.setSystemTime(new Date(NOW));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the control", () => {
  it("puts the EXACT count in the accessible name while the badge caps at 9+", () => {
    // The badge is decoration (`aria-hidden`), so the cap costs nothing and
    // keeps the 44px box from growing; the truth is in the name.
    mount({ unread: 14 });
    expect(bell()).toHaveAccessibleName(i18n.t("bell.labelUnread", { count: 14 }));
    expect(bell().textContent).toContain("9+");
    expect(bell().textContent).not.toContain("14");
  });

  it("renders no badge node at all when nothing is unread, and not a zero", () => {
    const { container } = mount({ unread: 0 });
    expect(bell()).toHaveAccessibleName(i18n.t("bell.label"));
    expect(container.querySelectorAll("span.rounded-full")).toHaveLength(0);
    expect(bell().textContent).toBe(i18n.t("bell.label"));
  });

  it("carries no live region, no haspopup and no expanded state", () => {
    // A five-second-cadence live region narrating a count is the hostility this
    // design refuses; a modal dialog is not a disclosure; and bare
    // `aria-haspopup` means "menu", which this is not.
    mount({ unread: 2 });
    expect(bell()).not.toHaveAttribute("aria-live");
    expect(bell()).not.toHaveAttribute("aria-expanded");
    expect(bell()).not.toHaveAttribute("aria-haspopup");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("is a 44px target — never Button size=sm, which is 36", () => {
    mount({ unread: 1 });
    expect(bell().className).toContain("min-h-11");
    expect(bell().className).toContain("min-w-11");
  });
});

describe("the panel", () => {
  it("renders each kind with its own sentence and an absolute Jerusalem time", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue({
      items: [
        row({ kind: "dispatch_assigned" }),
        row({ kind: "room_handed_over" }),
        row({ kind: "sos_targeted" }),
      ],
    });
    mount({ unread: 3 });
    await openPanel();

    expect(await screen.findByText(/הפנתה אליך לקוחה/)).toBeInTheDocument();
    expect(screen.getByText(/העבירה אליך חדר/)).toBeInTheDocument();
    expect(screen.getByText(/ביקשה עזרה/)).toBeInTheDocument();
    // 11:32Z is 14:32 in Jerusalem. Absolute, never «לפני 3 דקות».
    expect(screen.getAllByText("14:32")).toHaveLength(3);
  });

  it("SKIPS an unknown kind silently rather than rendering a raw enum", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue({
      items: [row(), row({ kind: "help_is_coming" })],
    });
    mount({ unread: 2 });
    await openPanel();

    expect(await screen.findByText(/הפנתה אליך לקוחה/)).toBeInTheDocument();
    expect(screen.queryByText(/help_is_coming/)).toBeNull();
  });

  it("renders the nameless variant when the actor's staff row is gone", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue({
      items: [row({ actor_name: null })],
    });
    mount({ unread: 1 });
    await openPanel();

    expect(await screen.findByText(i18n.t("bell.kindUnknownActor"))).toBeInTheDocument();
  });

  it("marks unread rows by WEIGHT and a text badge, never by colour alone", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue({
      items: [row(), row({ read_at: NOW })],
    });
    mount({ unread: 1 });
    await openPanel();

    const marker = await screen.findAllByText(i18n.t("bell.unreadMarker"));
    expect(marker).toHaveLength(1);
    expect(screen.getAllByText(/הפנתה אליך לקוחה/)[0].className).toContain("font-semibold");
  });

  it("gives sos_targeted rows NO button — they have no destination", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue({
      items: [row({ kind: "sos_targeted" })],
    });
    mount({ unread: 1 });
    await openPanel();

    await screen.findByText(/ביקשה עזרה/);
    // Only the footer's «סגירה» and «סמני הכל כנקרא» plus the bell itself.
    const rowButtons = screen
      .getAllByRole("button")
      .filter((one) => /ביקשה עזרה/.test(one.textContent ?? ""));
    expect(rowButtons).toEqual([]);
  });

  it("shows the cap note ONLY on a full page", async () => {
    const twenty = Array.from({ length: 20 }, () => row());
    vi.spyOn(api, "listNotifications").mockResolvedValue({ items: twenty });
    const { unmount } = mount({ unread: 20 });
    await openPanel();
    expect(await screen.findByText(i18n.t("bell.capNote"))).toBeInTheDocument();
    unmount();

    vi.spyOn(api, "listNotifications").mockResolvedValue({ items: twenty.slice(0, 19) });
    mount({ unread: 19 });
    await openPanel();
    await screen.findAllByText(/הפנתה אליך לקוחה/);
    expect(screen.queryByText(i18n.t("bell.capNote"))).toBeNull();
  });

  it("describes the dialog with the empty line so the sentence is not silent", async () => {
    // State E. Focus lands on a CONTROL, so a bare <p> is stepped over — the
    // description is what makes «אין התראות» reach a screen reader at all.
    vi.spyOn(api, "listNotifications").mockResolvedValue({ items: [] });
    const { container } = mount();
    await openPanel();

    const line = await screen.findByText(i18n.t("bell.empty"));
    const dialog = container.querySelector("dialog");
    expect(dialog?.getAttribute("aria-describedby")).toBe(line.id);
    expect(line.id).not.toBe("");
  });

  it("hides «mark all» when nothing on the page is unread", async () => {
    vi.spyOn(api, "listNotifications").mockResolvedValue({ items: [row({ read_at: NOW })] });
    mount();
    await openPanel();

    await screen.findByText(/הפנתה אליך לקוחה/);
    expect(screen.queryByRole("button", { name: i18n.t("bell.markAll") })).toBeNull();
  });
});

describe("failures", () => {
  it("announces a list failure on the FIRST render, with a retry", async () => {
    // F1. `role="alert"` immediately and unconditionally — the house
    // `{ns}.loadFailed` shape, and not one loadFailed in this console
    // distinguishes a first load from a retry.
    const read = vi.spyOn(api, "listNotifications").mockRejectedValue(new Error("boom"));
    mount({ unread: 1 });
    await openPanel();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("bell.loadFailed"));

    read.mockResolvedValue({ items: [row()] });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: i18n.t("bell.retry") }));
    });
    expect(await screen.findByText(/הפנתה אליך לקוחה/)).toBeInTheDocument();
  });

  it("rolls the optimistic zero back and announces bell.markFailed", async () => {
    // F2. The badge returns AND the rows go back to unread, so the «חדש» marker
    // and the count agree again — a half-rollback is the worse bug.
    vi.spyOn(api, "listNotifications").mockResolvedValue({ items: [row()] });
    const markRead = vi.fn().mockResolvedValue(new ApiError(500, "INTERNAL", "boom"));
    mount({ unread: 1, markRead });
    await openPanel();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: i18n.t("bell.markAll") }));
    });

    expect(await screen.findByText(i18n.t("bell.markFailed"))).toBeInTheDocument();
    expect(screen.getByText(i18n.t("bell.markFailed"))).toHaveAttribute("role", "alert");
    await waitFor(() => expect(bell().textContent).toContain("1"));
    expect(screen.getAllByText(i18n.t("bell.unreadMarker"))).toHaveLength(1);
  });
});

describe("a row click", () => {
  it("marks it read, opens the floor and closes the panel", async () => {
    const only = row();
    vi.spyOn(api, "listNotifications").mockResolvedValue({ items: [only] });
    const markRead = vi.fn().mockResolvedValue(null);
    const { onOpenFloor, container } = mount({ unread: 1, markRead });
    await openPanel();

    await act(async () => {
      fireEvent.click(await screen.findByRole("button", { name: /הפנתה אליך לקוחה/ }));
    });

    // ONE id — «she tapped it», not «mark all».
    expect(markRead).toHaveBeenCalledWith([only.id]);
    expect(onOpenFloor).toHaveBeenCalledOnce();
    expect(container.querySelector("dialog")?.open).not.toBe(true);
  });

  it("sends the RENDERED PAGE's ids on mark-all, and never an unseen row's", async () => {
    const unread = [row(), row()];
    vi.spyOn(api, "listNotifications").mockResolvedValue({
      items: [...unread, row({ read_at: NOW })],
    });
    const markRead = vi.fn().mockResolvedValue(null);
    mount({ unread: 2, markRead });
    await openPanel();

    await act(async () => {
      fireEvent.click(await screen.findByRole("button", { name: i18n.t("bell.markAll") }));
    });

    expect(markRead).toHaveBeenCalledWith(unread.map((one) => one.id));
  });
});
