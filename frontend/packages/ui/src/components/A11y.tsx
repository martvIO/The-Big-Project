import type { ReactNode } from "react";
import { cn, focusRing } from "../lib/styles";

export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>;
}

export interface SkipLinkProps {
  // Fragment target of the page's <main tabindex="-1">.
  href: string;
  children: ReactNode;
}

// First focusable element on every storefront page: hidden until focused, then
// jumps focus into the main content.
export function SkipLink({ href, children }: SkipLinkProps) {
  return (
    <a
      href={href}
      className={cn(
        "sr-only rounded-sm bg-surface-raised px-4 py-2 text-base text-ink",
        "focus:not-sr-only focus:absolute focus:inset-s-2 focus:top-2 focus:z-50 focus:shadow-md",
        focusRing,
      )}
    >
      {children}
    </a>
  );
}
