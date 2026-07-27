import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/styles";

export type BadgeVariant = "neutral" | "success" | "danger" | "muted" | "warning";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
}

// Every variant passes AA as text at the badge's text-xs size (the word carries
// the meaning, the outline is decorative). There is deliberately no `gold`
// variant: gold-strong is 3.80:1 — below the 4.5:1 text floor — and a Badge is
// always small text, so a gold marker uses `text-gold-text` inline instead.
const variants: Record<BadgeVariant, string> = {
  neutral: "border border-border text-ink",
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
