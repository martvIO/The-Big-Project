import { cn, focusRing } from "../lib/styles";

export interface PolicyBlockerBannerProps {
  message: string;
  actionLabel: string;
  onAction: () => void;
  className?: string;
}

// Warning-text on paper with a gold-strong inline-start stripe. No icon, not red
// — cautionary restraint, not an alarm.
export function PolicyBlockerBanner({ message, actionLabel, onAction, className }: PolicyBlockerBannerProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-md border-s-4 border-gold-strong bg-surface p-4 text-warning-text",
        className,
      )}
    >
      <p className="text-base">{message}</p>
      <button type="button" onClick={onAction} className={cn("self-start text-base text-gold-text underline", focusRing)}>
        {actionLabel}
      </button>
    </div>
  );
}
