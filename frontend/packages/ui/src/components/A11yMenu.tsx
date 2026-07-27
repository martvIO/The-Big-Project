import { useState } from "react";
import { cn, focusRing } from "../lib/styles";

export interface A11yStatementLinkProps {
  href: string;
  children: React.ReactNode;
  className?: string;
}

// Footer link to /accessibility (הצהרת נגישות), on every storefront page.
export function A11yStatementLink({ href, children, className }: A11yStatementLinkProps) {
  return (
    <a href={href} className={cn("text-sm text-gold-text underline", focusRing, className)}>
      {children}
    </a>
  );
}

export interface A11yMenuControls {
  contrast: string;
  textSize: string;
  readableFont: string;
  underlineLinks: string;
  stopMotion: string;
}

export interface A11yMenuProps {
  triggerLabel: string;
  controls: A11yMenuControls;
  // When a BookingCTA bar is present, clear it below 768 via the design token.
  hasBookingBar?: boolean;
  className?: string;
}

const CONTROL_ATTRS = [
  "data-a11y-contrast",
  "data-a11y-text-size",
  "data-a11y-readable-font",
  "data-a11y-underline-links",
  "data-a11y-stop-motion",
] as const;

// First-party accessibility menu (never a third-party overlay). Each control
// toggles a data attribute on <html>; theme.css styles the boost. Positioned to
// clear the BookingCTA bar below 768 using --space-a11y-clearance (PRE-1 fix).
export function A11yMenu({ triggerLabel, controls, hasBookingBar = false, className }: A11yMenuProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<Record<string, boolean>>({});

  const items: { attr: (typeof CONTROL_ATTRS)[number]; label: string }[] = [
    { attr: "data-a11y-contrast", label: controls.contrast },
    { attr: "data-a11y-text-size", label: controls.textSize },
    { attr: "data-a11y-readable-font", label: controls.readableFont },
    { attr: "data-a11y-underline-links", label: controls.underlineLinks },
    { attr: "data-a11y-stop-motion", label: controls.stopMotion },
  ];

  const toggle = (attr: string) => {
    setActive((prev) => {
      const next = !prev[attr];
      if (next) document.documentElement.setAttribute(attr, "");
      else document.documentElement.removeAttribute(attr);
      return { ...prev, [attr]: next };
    });
  };

  return (
    <div
      className={cn(
        "fixed end-4 z-50 [inset-block-end:var(--space-4)]",
        hasBookingBar && "max-md:[inset-block-end:var(--space-a11y-clearance)]",
        className,
      )}
    >
      {open && (
        <div className="absolute bottom-full end-0 mb-2 w-60 rounded-md bg-surface-raised p-2 shadow-lg">
          {items.map((item) => (
            <button
              key={item.attr}
              type="button"
              role="menuitemcheckbox"
              aria-checked={Boolean(active[item.attr])}
              onClick={() => toggle(item.attr)}
              className={cn(
                "flex w-full items-center justify-between rounded-sm px-3 py-2 text-start text-base text-ink hover:bg-surface",
                focusRing,
              )}
            >
              <span>{item.label}</span>
              {active[item.attr] && <span aria-hidden="true">✓</span>}
            </button>
          ))}
        </div>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-label={triggerLabel}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex size-11 items-center justify-center rounded-full bg-surface-raised text-ink shadow-md",
          focusRing,
        )}
      >
        <span aria-hidden="true">◑</span>
      </button>
    </div>
  );
}
