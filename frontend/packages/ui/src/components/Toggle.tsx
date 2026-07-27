import { useId } from "react";
import { cn, focusRing } from "../lib/styles";

export interface ToggleProps {
  label: string;
  description?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}

// Native checkbox with role="switch" — full keyboard + AT support for free.
export function Toggle({ label, description, checked, onCheckedChange, disabled = false }: ToggleProps) {
  const id = useId();
  const descId = description ? `${id}-desc` : undefined;

  return (
    <label htmlFor={id} className="flex items-start gap-3">
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
