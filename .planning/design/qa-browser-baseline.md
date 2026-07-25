# Browser QA Baseline — pre-F9-build

**Run**: 2026-07-24 · **Tool**: Playwright 1.61.1 / Chromium 1228, headless · **Locale**: he-IL
**Targets**: `apps/storefront` (vite :5173) · `apps/manage` (vite :5174) — dev servers started for the run and stopped after
**Viewports**: 1440×900 · 768×1024 · 375×812 · plus a `prefers-reduced-motion: reduce` pass
**Raw data**: measurements re-runnable via the script pattern below; screenshots captured at all three widths per app

## What was actually tested

Both apps currently render a single centred placeholder — one `<h1>` and one `<p>`. There is no catalog, no console, no form, no navigation. So this is a **baseline**, not a design-conformance pass: it establishes what is true today and gives the F9 build a measured starting line.

## Summary

| | storefront | manage |
|---|---|---|
| Console errors | 0 | 0 |
| Uncaught page errors | 0 | 0 |
| Failed requests | 0 | 0 |
| Responses ≥400 | 0 | 0 |
| Horizontal scroll @1440/768/375 | none | none |
| `lang` / `dir` | `he` / `rtl` ✓ | `he` / `rtl` ✓ |
| Viewport meta | `width=device-width, initial-scale=1.0` ✓ | ✓ |
| `<main>` landmark | present ✓ | present ✓ |
| `h1` count | 1 ✓ | 1 ✓ |
| Focusable elements | **0** | **0** |
| Skip link | **absent** | n/a (console) |
| הצהרת נגישות link | **absent** | n/a |
| Loaded font faces | **0** | **0** |
| External font `<link>`s | 0 ✓ | 0 ✓ |
| Animated elements (reduced-motion) | 0 ✓ | 0 ✓ |

## BUG-1 — Gold text on cream fails AA, measured at 2.38:1 · **major**

- **Where**: both apps, the subtitle `<p>` — [storefront App.tsx:14](../../Frontend/apps/storefront/src/App.tsx#L14), [manage App.tsx:14](../../Frontend/apps/manage/src/App.tsx#L14)
- **Measured**: `#C5A059` on `#FDFBF7` at 14px/400 → **2.38:1**. WCAG AA needs **4.5:1** for normal text.
- **Expected**: `--color-gold` is decorative-only. Text gold is `--color-gold-text` `#7F612B` (5.57:1).
- **Note**: 2.38:1 is *exactly* the figure tokens.md computed by hand — the token doc's arithmetic is confirmed correct by measurement. The violation is in the code, not the design.
- **Fix**: `--color-gold-text`, or delete the placeholder line with the F9 build.

## BUG-2 — Hebrew heading renders at weight 300 · **major**

- **Where**: both apps, the `<h1>` (`font-light`)
- **Measured**: computed `font-weight: 300`
- **Expected**: tokens.md weight law — "body UI text 400, emphasis 600, **never 300** (Hebrew thins badly)"; display font never below 400.

## BUG-3 — Letter-spacing applied to Hebrew · **major**

- **Where**: both apps, the `<h1>` (`tracking-wide`)
- **Measured**: computed `letter-spacing: 0.75px` on Hebrew text
- **Expected**: "Letter-spacing: 0 for Hebrew (tracking breaks Hebrew)". Non-zero tracking is permitted only on Latin-only all-caps micro-labels.

## BUG-4 — Neither brand font loads; Hebrew renders in a system sans · **major**

- **Where**: both apps, every text node
- **Measured**: `document.fonts` is **empty** (0 faces). Computed family resolves to `-apple-system, system-ui, "Segoe UI", Roboto, …` — the Tailwind preflight default stack.
- **Expected**: `--font-display: "Frank Ruhl Libre", "David Libre", serif` and `--font-body: "Assistant", "Heebo", system-ui, sans-serif`, self-hosted via `@fontsource`.
- **Why it matters**: this is the exact failure [test-results.md](test-results.md) hard-stops usability sessions over — "the display serif silently falls back to a system sans and the quiet-luxury register — the thing under test — is simply not on screen." It looks like a plain heading, not like a bug.

## BUG-5 — Heading size is Tailwind's default, not the token · **minor**

- **Measured**: `font-size: 30px` (Tailwind `text-3xl` = 1.875rem)
- **Expected**: `--text-3xl` = 2.25rem = **36px**. Confirms the token scale is not wired into Tailwind yet.

## WARN-1 — Zero focusable elements in either app

No links, buttons, or inputs exist yet, so there is nothing to keyboard-test and no focus ring to verify. Consequently **no skip link** and **no הצהרת נגישות footer link** — both mandatory on every storefront page per IS 5568 and the component inventory. Expected at this stage; they are F9/F10 build obligations, tracked in the checklist.

## WARN-2 — Document titles are English and static

`Boutique Platform — Storefront` / `Boutique Platform — ניהול`. Per-route Hebrew titles are a **WCAG 2.0 Level A** obligation (2.4.2) and a Vite SPA keeps `index.html`'s title across client navigation unless set explicitly.

## Passed

- No console errors, page errors, or failed/4xx/5xx requests in either app
- No horizontal scroll at 1440, 768, or 375
- `lang="he" dir="rtl"` correct on both documents; viewport meta present, no `user-scalable=no`
- One `<main>` and exactly one `<h1>` per app — the built apps already satisfy two of the four `landmark`/`heading` findings the axe baseline raised against the prototype
- Ink on cream measured **15.24:1**, matching tokens.md exactly
- No runtime Google Fonts request (the CDN dependency is confined to the prototypes, as intended)
- Reduced-motion pass renders correctly with zero animated elements

## Re-running

```bash
cd Frontend/apps/storefront && ./node_modules/.bin/vite --port 5173 --strictPort &
cd Frontend/apps/manage    && ./node_modules/.bin/vite --port 5174 --strictPort &
# then drive Chromium and read computed styles; contrast = WCAG relative luminance on
# color vs nearest non-transparent ancestor background
```

Playwright is not a workspace dependency — it resolved from the npx cache (1.61.1, matching installed chromium-1228). **Add `@playwright/test` to the workspace with the F9 build** so this is reproducible in CI rather than dependent on a developer's cache.
