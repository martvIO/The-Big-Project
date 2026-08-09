import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConsoleShell } from "../components/ConsoleShell";
import { SetupProgress } from "../components/SetupProgress";
import { PolicyBlockerBanner } from "../components/PolicyBlockerBanner";

const nav = [
  { key: "profile", label: "פרופיל" },
  { key: "hours", label: "שעות" },
  { key: "catalog", label: "שמלות" },
];

describe("ConsoleShell", () => {
  it("marks the active nav item with aria-current=page (not role=tab)", () => {
    render(
      <ConsoleShell
        boutiqueName="בוטיק כלה"
        title="ניהול הבוטיק"
        logoutLabel="יציאה"
        onLogout={() => {}}
        skipLinkLabel="דלג לתוכן"
        nav={nav}
        activeKey="hours"
        onNavigate={() => {}}
      >
        <p>תוכן</p>
      </ConsoleShell>,
    );
    const active = screen.getByRole("button", { name: "שעות" });
    expect(active).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "ניהול הבוטיק" })).toBeInTheDocument();
  });

  it("routes nav clicks and logout through their callbacks", () => {
    const onNavigate = vi.fn();
    const onLogout = vi.fn();
    render(
      <ConsoleShell
        boutiqueName="ב" title="t" logoutLabel="יציאה" onLogout={onLogout}
        skipLinkLabel="דלג" nav={nav} activeKey="profile" onNavigate={onNavigate}
      >
        <p>x</p>
      </ConsoleShell>,
    );
    fireEvent.click(screen.getByRole("button", { name: "שמלות" }));
    expect(onNavigate).toHaveBeenCalledWith("catalog");
    fireEvent.click(screen.getByRole("button", { name: "יציאה" }));
    expect(onLogout).toHaveBeenCalledOnce();
  });

  // F35's slot. The shell knows nothing about the control — `guide`'s shipped
  // contract verbatim — so the only things worth asserting are that it lands in
  // the chrome group, that it lands BEFORE the guide, and that omitting it
  // writes nothing at all.
  it("renders the bell inside the chrome group, before the guide", () => {
    render(
      <ConsoleShell
        boutiqueName="ב" title="t" logoutLabel="יציאה" onLogout={() => {}}
        skipLinkLabel="דלג" nav={nav} activeKey="profile" onNavigate={() => {}}
        bell={<button type="button">התראות</button>}
        guide={<button type="button">מדריך</button>}
      >
        <p>x</p>
      </ConsoleShell>,
    );
    const bell = screen.getByRole("button", { name: "התראות" });
    const guide = screen.getByRole("button", { name: "מדריך" });
    const logout = screen.getByRole("button", { name: "יציאה" });
    // One wrapper, three children — the row stays two groups and does not
    // re-spread (the ⚠ comment on that div is the reason it exists).
    expect(bell.parentElement).toBe(guide.parentElement);
    expect(bell.parentElement).toBe(logout.parentElement);
    // RTL reading order: bell, guide, logout — so the bell is first in the
    // chrome group's tab order with no tabindex anywhere.
    expect(bell.compareDocumentPosition(guide) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("writes no node at all when bell is omitted", () => {
    const { container } = render(
      <ConsoleShell
        boutiqueName="ב" title="t" logoutLabel="יציאה" onLogout={() => {}}
        skipLinkLabel="דלג" nav={nav} activeKey="profile" onNavigate={() => {}}
        guide={<button type="button">מדריך</button>}
      >
        <p>x</p>
      </ConsoleShell>,
    );
    const chrome = screen.getByRole("button", { name: "מדריך" }).parentElement;
    expect(chrome?.children).toHaveLength(2);
    expect(container.querySelectorAll("button")).toHaveLength(2 + nav.length);
  });
});

describe("SetupProgress", () => {
  const items = [
    { key: "profile", label: "פרופיל", done: true },
    { key: "hours", label: "שעות", done: true },
    { key: "types", label: "סוגי תורים", done: false },
    { key: "policy", label: "מדיניות", done: false },
  ];

  it("interpolates the derived count and points at the first incomplete section", () => {
    const onGoTo = vi.fn();
    render(
      <SetupProgress
        items={items}
        headingLabel="הגדרה ראשונית"
        countLabel={(d, t) => `${d}/${t} הושלמו`}
        onGoTo={onGoTo}
        goToLabel="להשלמה"
      />,
    );
    expect(screen.getByText("2/4 הושלמו")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "להשלמה" }));
    expect(onGoTo).toHaveBeenCalledWith("types");
  });

  it("renders at 0/4 and 4/4 too", () => {
    const { rerender } = render(
      <SetupProgress items={items.map((i) => ({ ...i, done: false }))} headingLabel="h" countLabel={(d, t) => `${d}/${t}`} onGoTo={() => {}} />,
    );
    expect(screen.getByText("0/4")).toBeInTheDocument();
    rerender(
      <SetupProgress items={items.map((i) => ({ ...i, done: true }))} headingLabel="h" countLabel={(d, t) => `${d}/${t}`} onGoTo={() => {}} />,
    );
    expect(screen.getByText("4/4")).toBeInTheDocument();
  });
});

describe("PolicyBlockerBanner", () => {
  it("shows the message and routes its action", () => {
    const onAction = vi.fn();
    render(<PolicyBlockerBanner message="נדרשת מדיניות ביטול" actionLabel="ליצירת מדיניות" onAction={onAction} />);
    expect(screen.getByText("נדרשת מדיניות ביטול")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ליצירת מדיניות" }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});
