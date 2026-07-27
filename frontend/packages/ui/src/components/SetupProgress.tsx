import { cn, focusRing } from "../lib/styles";
import { Card } from "./Card";

export interface SetupProgressItem {
  key: string;
  label: string;
  done: boolean;
}

export interface SetupProgressProps {
  items: SetupProgressItem[];
  headingLabel: string;
  // Interpolates the derived counts, e.g. (d,t) => `${d}/${t} הושלמו` — no
  // hardcoded "3/4" anywhere.
  countLabel: (done: number, total: number) => string;
  // Opens the section it names (the first incomplete one). Never an href="#".
  onGoTo: (key: string) => void;
  goToLabel?: string;
  className?: string;
}

// Derived, never authored — ticks come from the section responses. Renders
// correctly at any done/total; the label interpolates the counts.
export function SetupProgress({ items, headingLabel, countLabel, onGoTo, goToLabel, className }: SetupProgressProps) {
  const done = items.filter((i) => i.done).length;
  const total = items.length;
  const firstIncomplete = items.find((i) => !i.done);

  return (
    <Card className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-baseline justify-between">
        <span className="font-display text-lg text-ink">{headingLabel}</span>
        <span className="text-sm text-ink-muted">{countLabel(done, total)}</span>
      </div>
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item.key} className="flex items-center gap-2 text-base text-ink">
            <span aria-hidden="true" className={item.done ? "text-success" : "text-ink-muted"}>
              {item.done ? "✓" : "○"}
            </span>
            <span className={item.done ? "text-ink" : "text-ink-muted"}>{item.label}</span>
          </li>
        ))}
      </ul>
      {firstIncomplete && goToLabel && (
        <button
          type="button"
          onClick={() => onGoTo(firstIncomplete.key)}
          className={cn("self-start text-sm text-gold-text underline", focusRing)}
        >
          {goToLabel}
        </button>
      )}
    </Card>
  );
}
