import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/styles";

export type BadgeVariant = "neutral" | "gold" | "success" | "danger" | "muted" | "warning";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
}

// All variants pass AA as text except `gold` (gold-strong, 3.80:1) which is
// large-text-only by contract — the word carries the meaning, the outline is
// decorative.
const variants: Record<BadgeVariant, string> = {
  neutral: "border border-border text-ink",
  gold: "border border-gold-strong text-gold-strong",
  success: "border border-success text-success",
  danger: "border border-danger text-danger",
  muted: "border border-border text-ink-muted",
  warning: "border border-border text-warning-text font-semibold",
};

export function Badge({ variant = "neutral", className, children, ...rest }: BadgeProps) {
  return (
    <span
      {...rest}
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
