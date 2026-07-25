import type { ReactNode } from "react";
import { cn, focusRing } from "../lib/styles";
import { SkipLink } from "./A11y";

export interface ConsoleNavItem {
  key: string;
  label: string;
}

export interface ConsoleShellProps {
  boutiqueName: string;
  title: string; // the console h1
  logoutLabel: string;
  onLogout: () => void;
  skipLinkLabel: string;
  nav: ConsoleNavItem[];
  activeKey: string;
  onNavigate: (key: string) => void;
  banner?: ReactNode;
  progress?: ReactNode;
  children: ReactNode;
}

// Owner console frame. Navigation is contract (b): a plain <nav> with
// aria-current="page" (NEVER role="tab" without the full keyboard contract). The
// active item carries a gold-strong underline AND aria-current, so the state is
// never signalled by colour alone.
export function ConsoleShell({
  boutiqueName,
  title,
  logoutLabel,
  onLogout,
  skipLinkLabel,
  nav,
  activeKey,
  onNavigate,
  banner,
  progress,
  children,
}: ConsoleShellProps) {
  return (
    <div className="min-h-screen bg-bg text-ink">
      <SkipLink href="#console-main">{skipLinkLabel}</SkipLink>

      <header className="border-b border-border">
        <div className="mx-auto flex max-w-[720px] items-center justify-between px-4 py-3">
          <span className="font-display text-lg text-ink">{boutiqueName}</span>
          <button type="button" onClick={onLogout} className={cn("text-sm text-ink-muted hover:text-ink", focusRing)}>
            {logoutLabel}
          </button>
        </div>
        <nav className="mx-auto max-w-[720px] px-4">
          <ul className="flex flex-wrap gap-4">
            {nav.map((item) => {
              const active = item.key === activeKey;
              return (
                <li key={item.key}>
                  <button
                    type="button"
                    aria-current={active ? "page" : undefined}
                    onClick={() => onNavigate(item.key)}
                    className={cn(
                      "border-b-2 py-2 text-base",
                      active ? "border-gold-strong font-semibold text-ink" : "border-transparent text-ink-muted hover:text-ink",
                      focusRing,
                    )}
                  >
                    {item.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>

      <main id="console-main" tabIndex={-1} className="mx-auto flex max-w-[720px] flex-col gap-6 px-4 py-6">
        <h1 className="sr-only">{title}</h1>
        {banner}
        {progress}
        {children}
      </main>
    </div>
  );
}
