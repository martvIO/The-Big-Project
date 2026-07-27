import type { ReactNode } from "react";
import { cn } from "../lib/styles";

export interface BookingCTAProps {
  children: ReactNode;
  className?: string;
}

// Persistent bottom bar below 768 (footprint = --cta-bar-height: 56px button +
// space-3 top/bottom = 80px), inline from 768 up. Pages reserve matching
// bottom padding so the bar never overlaps content (see --cta-bar-height).
export function BookingCTA({ children, className }: BookingCTAProps) {
  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 border-t border-border bg-bg p-3",
        "md:static md:inset-auto md:border-0 md:bg-transparent md:p-0",
        className,
      )}
    >
      {children}
    </div>
  );
}
