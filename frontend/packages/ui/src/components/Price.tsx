import { cn } from "../lib/styles";

export interface PriceProps {
  // Stored in agorot (integer). Conversion to shekels happens once, here.
  agorot: number;
  visible: boolean;
  // "מחיר בתיאום" — supplied by the app's i18n, never hardcoded in this package.
  hiddenLabel: string;
  className?: string;
}

// THE only way to render money. Format is number-then-shekel ("5,900 ₪") with
// the run LTR-isolated (bdi + dir="ltr") so digits and the ₪ read correctly
// inside RTL text. The hidden-price label occupies the same slot at the same
// height, so a mixed grid never jumps.
export function Price({ agorot, visible, hiddenLabel, className }: PriceProps) {
  if (!visible) {
    return <span className={cn("font-body text-base italic text-ink-muted", className)}>{hiddenLabel}</span>;
  }

  const shekels = agorot / 100;
  const formatted = new Intl.NumberFormat("he-IL", {
    minimumFractionDigits: agorot % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(shekels);

  return (
    <bdi dir="ltr" className={cn("font-body text-base text-ink", className)}>
      {formatted} ₪
    </bdi>
  );
}
