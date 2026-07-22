// PLACEHOLDER tokens carried from the PRD palette. The binding design-token set
// (full palette, typography, spacing, AA-contrast-resolved text colors) lands at
// the Feature 9 design gate in .planning/design/system/tokens.md — do not extend
// this object ad hoc before that.
export const tokens = {
  color: {
    cream: "#FDFBF7",
    gold: "#C5A059",
    ink: "#2B2118",
  },
} as const;

export type Tokens = typeof tokens;
