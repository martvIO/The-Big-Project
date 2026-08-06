import { useId } from "react";
import { cn, focusRing } from "../lib/styles";

export interface ToggleProps {
  label: string;
  description?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  // ⚠ LANDS ON THE <label>, WHICH IS THE HIT TARGET — the `size-5` checkbox box
  // is 20px and is NOT. A caller that needs the 44px floor (F-W1) has to be able
  // to reach the label, so `min-h-11` on a wrapper element would not do it.
  className?: string;
}

// Native checkbox with role="switch" — full keyboard + AT support for free.
export function Toggle({
  label,
  description,
  checked,
  onCheckedChange,
  disabled = false,
  className,
}: ToggleProps) {
  const id = useId();
  const descId = description ? `${id}-desc` : undefined;

  return (
    <label htmlFor={id} className={cn("flex items-start gap-3", className)}>
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        aria-describedby={descId}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className={cn(
          "mt-0.5 size-5 shrink-0 rounded-sm border border-border-input accent-gold-strong",
          "disabled:cursor-not-allowed disabled:opacity-60",
          focusRing,
        )}
      />
      <span className="flex flex-col">
        <span className="text-base text-ink">{label}</span>
        {description && (
          <span id={descId} className="text-sm text-ink-muted">
            {description}
          </span>
        )}
      </span>
    </label>
  );
}
