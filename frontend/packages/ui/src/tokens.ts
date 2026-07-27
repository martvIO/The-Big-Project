// Mirror of the @theme block in theme.css. theme.css is the single source of
// truth; a Vitest (tokens.test.ts) parses that block and asserts this object
// matches it key-for-key, so drift is a red test, not a silent divergence.
// This TS copy exists for non-CSS consumers (canvas, meta tags, JS that can't
// read a CSS custom property at module scope).
export const themeTokens = {
  "--color-bg": "#FDFBF7",
  "--color-surface": "#F6F0E6",
  "--color-surface-raised": "#FFFFFF",
  "--color-ink": "#2B2118",
  "--color-ink-muted": "#6B5D4F",
  "--color-gold": "#C5A059",
  "--color-gold-strong": "#9E7B36",
  "--color-gold-text": "#7F612B",
  "--color-border": "#E4DACA",
  "--color-border-input": "#8A7A5E",
  "--color-success": "#2E6B4F",
  "--color-danger": "#A03232",
  "--color-warning-text": "#8A5A1E",
  "--color-focus": "#7F612B",

  "--font-display": '"Frank Ruhl Libre", "David Libre", serif',
  "--font-body": '"Assistant", "Heebo", system-ui, sans-serif',

  "--text-xs": "0.75rem",
  "--text-xs--line-height": "1.4",
  "--text-sm": "0.875rem",
  "--text-sm--line-height": "1.5",
  "--text-base": "1rem",
  "--text-base--line-height": "1.6",
  "--text-lg": "1.1875rem",
  "--text-lg--line-height": "1.5",
  "--text-xl": "1.4375rem",
  "--text-xl--line-height": "1.35",
  "--text-2xl": "1.75rem",
  "--text-2xl--line-height": "1.25",
  "--text-3xl": "2.25rem",
  "--text-3xl--line-height": "1.15",

  "--space-1": "4px",
  "--space-2": "8px",
  "--space-3": "12px",
  "--space-4": "16px",
  "--space-6": "24px",
  "--space-8": "32px",
  "--space-12": "48px",
  "--space-16": "64px",

  "--radius-sm": "4px",
  "--radius-md": "8px",
  "--radius-full": "9999px",

  "--shadow-sm": "0 1px 2px rgb(43 33 24 / 0.06)",
  "--shadow-md": "0 4px 12px rgb(43 33 24 / 0.10)",
  "--shadow-lg": "0 12px 32px rgb(43 33 24 / 0.14)",

  "--ease-out": "cubic-bezier(0.16, 1, 0.3, 1)",

  "--motion-fast": "150ms",
  "--motion-base": "200ms",
  "--motion-slow": "300ms",

  "--animate-skeleton": "skeleton-pulse 1.5s ease-in-out infinite",
  "--animate-toast": "toast-in var(--motion-slow) var(--ease-out)",
  "--animate-modal-panel": "modal-panel var(--motion-base) var(--ease-out)",
  "--animate-modal-backdrop": "modal-backdrop var(--motion-fast) var(--ease-out)",

  "--cta-bar-height": "calc(56px + 2 * var(--space-3))",
  "--space-a11y-clearance": "calc(var(--cta-bar-height) + var(--space-3))",
} as const;

// Ergonomic accessor for the colors non-CSS code reaches for (theme-color meta
// tag, canvas monogram fills). Values are pinned to themeTokens by the parity test.
export const tokens = {
  color: {
    bg: "#FDFBF7",
    surface: "#F6F0E6",
    surfaceRaised: "#FFFFFF",
    ink: "#2B2118",
    inkMuted: "#6B5D4F",
    gold: "#C5A059",
    goldStrong: "#9E7B36",
    goldText: "#7F612B",
    border: "#E4DACA",
    borderInput: "#8A7A5E",
    success: "#2E6B4F",
    danger: "#A03232",
    warningText: "#8A5A1E",
    focus: "#7F612B",
  },
} as const;

export type ThemeTokens = typeof themeTokens;
export type Tokens = typeof tokens;
