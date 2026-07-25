export type ClassValue = string | false | null | undefined;

// Minimal className joiner — no clsx dependency for a handful of conditionals.
export function cn(...values: ClassValue[]): string {
  return values.filter(Boolean).join(" ");
}

// The one focus ring for every interactive element: 2px --color-focus, 2px
// offset, never removed (tokens.md usage law 4). focus-visible so it shows for
// keyboard, not mouse.
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
