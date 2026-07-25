import { cn } from "../lib/styles";

export type SkeletonVariant = "text" | "image" | "block";

export interface SkeletonProps {
  variant?: SkeletonVariant;
  // For variant="text": number of shimmer lines.
  lines?: number;
  className?: string;
}

const bar = "animate-skeleton rounded-sm bg-border";

// Pulse comes from --animate-skeleton (1.5s); the global reduced-motion block in
// theme.css freezes it. Decorative — hidden from AT.
export function Skeleton({ variant = "block", lines = 3, className }: SkeletonProps) {
  if (variant === "text") {
    return (
      <div className="flex flex-col gap-2" aria-hidden="true">
        {Array.from({ length: lines }).map((_, i) => (
          <span key={i} className={cn(bar, "h-4", i === lines - 1 && "w-2/3", className)} />
        ))}
      </div>
    );
  }
  if (variant === "image") {
    return <div aria-hidden="true" className={cn(bar, "aspect-[3/4] w-full", className)} />;
  }
  return <div aria-hidden="true" className={cn(bar, "h-full w-full", className)} />;
}
