import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { cn, focusRing } from "../lib/styles";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidthMobile?: boolean;
  loading?: boolean;
  ref?: Ref<HTMLButtonElement>;
  children: ReactNode;
}

// `transition` (not transition-colors) so the primary variant's elevation
// affordance animates too; duration + easing resolve to motion tokens.
const base =
  "relative inline-flex items-center justify-center rounded-md font-body font-semibold " +
  "transition duration-(--motion-fast) ease-out disabled:cursor-not-allowed disabled:opacity-60";

const variants: Record<ButtonVariant, string> = {
  // Hover keeps ink on gold — 6.41:1, same as rest. The old hover (gold-strong
  // background, white label) measured 3.93:1, under the 4.5 floor, and mobile
  // browsers leave :hover stuck after a tap so a bride sat looking at it. Gold
  // is an accent: gold-strong carries no text at any size (tokens.md), and no
  // token is dark enough to darken under ink and still clear 4.5 — so the hover
  // affordance is elevation, not a colour swap.
  primary: "bg-gold text-ink hover:shadow-md",
  secondary: "border border-ink bg-transparent text-ink hover:bg-surface",
  ghost: "bg-transparent text-ink hover:bg-surface",
  danger: "bg-danger text-surface-raised hover:opacity-90",
};

const sizes: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 text-sm",
  md: "min-h-11 px-4 text-base",
  lg: "min-h-12 px-6 text-lg",
};

export function Button({
  variant = "primary",
  size = "md",
  fullWidthMobile = false,
  loading = false,
  disabled,
  children,
  className,
  ref,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      ref={ref}
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        base,
        variants[variant],
        sizes[size],
        focusRing,
        fullWidthMobile && "w-full sm:w-auto",
        className,
      )}
    >
      {/* Label stays in the DOM while loading (aria-hidden) so the button keeps
          its natural width — the spinner is overlaid, width never jumps. */}
      <span className={cn("inline-flex items-center gap-2", loading && "invisible")} aria-hidden={loading || undefined}>
        {children}
      </span>
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center" aria-hidden="true">
          <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        </span>
      )}
    </button>
  );
}
