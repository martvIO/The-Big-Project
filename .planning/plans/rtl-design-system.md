# Plan: RTL Design System & Tokens (F9)

**Created**: 2026-07-25 · **Status**: done — PR #12 merged 2026-07-27 (user directive 2026-07-25 waived the interview gate to start the build) · **Effort**: L
**Design package**: [../design/screens/design-system/README.md](../design/screens/design-system/README.md) (gate PASSED rev 2) · **Build gate**: [../design/qa-checklist.md](../design/qa-checklist.md) (rev 2)
**Epic**: E2 #9 · **Branch**: `feature/rtl-design-system` (worktree). Frontend-only — **backend router diff must be empty** at PR time.
Binding sources: `design/system/tokens.md` · `design/system/components.md` · `design/qa-checklist.md` · `design/screens/design-system/manage-restyle.md` · `design/screens/manage-catalog/manage-catalog.md` §12. Where plan and amended design docs disagree, the docs win.

TDD red-before-green; one batch commit per phase; one fix commit per review round. Repo path has a space and `+` — quote everything; committed path literals use git-lowercase `frontend/`. Stack is React 19 / Vite 8 / Tailwind v4 / FastAPI — the `.claude/rules/` Kotlin/Micronaut conventions do NOT apply here.

## Build progress (2026-07-25)

Branch `feature/rtl-design-system`, all commits green (lint + typecheck + build + test).

| Phase | State | Commit |
|---|---|---|
| Setup | done — worktree, rev-2 qa docs to main, green baseline (103 manage tests) | `e8fd318` |
| 0 — design amendments | done — tokens/qa/components/manage-restyle amended; **design-critic re-run ACCEPT** | `2b21362`, `1be1b1a` |
| 1 — foundation | done — theme.css (@theme, 7 paired leadings, ease-out override, color-scheme, PRE-1 tokens), tokens.ts mirror + parity test, @fontsource (Hebrew woff2 verified in build), i18n both apps, storefront App.tsx baseline fix | `0b82b97` |
| 2 — primitives | done — 14 components (Button/Input/TextArea/Select/Toggle/Time+DateField/Badge/Card/Toast/Modal/Skeleton/EmptyState/SectionHeading/A11y) | `43359da` |
| 3 — storefront composites | done — hours.ts (Asia/Jerusalem, grouping fixture, next-open), Price, HoursTable, BoutiqueHeader, DressCard, DressGrid, Gallery, BookingCTA, ContactPanel, A11yMenu — **61 ui tests** | `a909527` |
| 4a — console composites | done — ConsoleShell, SetupProgress, PolicyBlockerBanner | `44d2ec4` |
| 4b — manage integration | done — `shared.tsx` deleted, all 9 sections onto `@boutique/ui`, confirm `Modal` interstitials, `SetupProgress`/`PolicyBlockerBanner` wired | `7c74b2a` |
| 5 — QA gate | done — §11 grep block, `@playwright/test` + `@axe-core/playwright`, CI e2e job | `261882e` |
| 6 — ship | done — dual review round 1 (security + quality) addressed, stray `.gitignore` `lib/` rule fixed, PR #12 merged 2026-07-27 | `bfa6e6e`, `53ee94f` |

**`packages/ui` is complete** — every component in components.md, 61 tests, RTL-clean (zero physical-direction props), zero motion literals in component code, no hardcoded Hebrew (strings via props).

### Shipped
PR #12 merged 2026-07-27. Epic F9 → done. The `qa-checklist.md` boxes were not walked box-by-box as part of the merge (CI covers lint/typecheck/build/test/e2e+axe; the manual/browser rows are unticked) — a follow-up if a full audit is wanted later.

## Phase 0 — Design amendments + critic re-run (S) — DONE
tokens.md §12 items 3a–3e (border-input `#B9A98F`→`#8A7A5E`; focus 4.86→5.57; gold-strong barred from rendered text; radius chips→`--radius-full`; added contrast pairs; PRE-1 `--cta-bar-height`/`--space-a11y-clearance` tokens); qa-checklist §8 figure; components.md Badge `muted`+`warning`; manage-restyle.md five-tab shell + F8 component rows + nav semantics + new states. design-critic re-run over amended docs (ACCEPT required for §9 PRE-1 ticks).

## Phase 1 — Foundation (M)
`packages/ui` toolchain (react/vitest/Testing Library devDeps, `peerDependencies.react ^19`, `exports` for `.` + `./theme.css`, `"test": "TZ=America/New_York vitest run"`, keep oxlint `-c`); `theme.css` single `@theme` block (all corrected tokens, 7 paired `--text-*--line-height`, `--ease-out` override, `color-scheme: only light`, `font-synthesis: none`, reduced-motion block retaining scroll-snap); `@fontsource/frank-ruhl-libre` {400,500,700} + `@fontsource/assistant` {400,600,700}; `tokens.ts` checked-in mirror + `tokens.test.ts` parity test (parses `@theme`, asserts key/value parity — drift is a red test); i18next+react-i18next in both apps (Hebrew only, ui strings via props); both apps `@import "@boutique/ui/theme.css"`; storefront `App.tsx` rewritten to kill the 4 baseline violations. Stage `pnpm-lock.yaml`.

## Phase 2 — Core primitives (L)
`packages/ui/src/components/*.tsx` + `__tests__/`. Button (loading locks width), Input/TextArea (label required by types, `aria-describedby`, `dir` override), Select, Toggle, TimeField/DateField, Badge (6 variants), Card, Toast (roles + one-at-a-time), Modal (native `<dialog>`, Esc no-callback, focus return, two-element motion), Skeleton (1.5s, static under reduced-motion), EmptyState, SectionHeading, A11y (VisuallyHidden/SkipLink/focus-ring). Motion grep = 1 hit; physical-property greps empty.

## Phase 3 — Storefront composites (L)
`hours.ts` pure fns (`Asia/Jerusalem`, grouping fixture 5 rows never `א׳–ה׳`, `נפתח מחר` only when literally tomorrow, 23:00→00:30 flip); Price (agorot→shekel once, LTR isolation, hidden-price same slot); HoursTable (Sat→`סגור`); BoutiqueHeader (closed-today ink not danger); DressCard (aspect-ratio CLS 0, reserved not dimmed, favorites slot no button, image-missing no `<img>`, fade-in cached path); DressGrid (2/3/4, gap tokens); Gallery (RTL snap, keyboard+AT, no autoplay); BookingCTA (`--cta-bar-height`); ContactPanel; A11yStatementLink + A11yMenu (`--space-a11y-clearance`).

## Phase 4 — Manage restyle (M/L)
F7/F8 APIs/behavior/tests frozen. ConsoleShell (plain nav + `aria-current`, accordion ≤767, `h1`, SkipLink+`<main tabindex=-1>`), SetupProgress (derived 0/4..4/4, `{done}/{total}`, no `href="#"`), PolicyBlockerBanner. Section restyles (LoginForm verbatim error, ProfileSection, HoursSection, TypesSection ₪ adornment, TermsSection units-in-labels, F8 sections). Save flow (loading width-locked, inline `נשמר לפני רגע`, error Toast). Destructive interstitials via `Modal` preserving F8 accessible names. **Delete `shared.tsx`.** i18n keys extracted per component.

## Phase 5 — QA gate (M)
qa §11 grep block; `pnpm -r lint/typecheck/build/test`; `@playwright/test` + `@axe-core/playwright` at `frontend/` root (`e2e/`), CI step; automated axe + Hebrew-woff2-fetched + `color-scheme` + no-h-scroll + Hebrew titles; manual `/spartan:qa` console keyboard/resize/PRE-1 passes; storefront page rows deferred to F10 QA (annotate). Tick checklist; re-measure baseline.

## Phase 6 — Ship (S)
Dual review: phase-reviewer (token fidelity, F7/F8 freeze, coverage) + adversarial security (no new endpoints, links from validated values, i18next escaping, lockfile pins). One fix commit/round. PR → `gh pr checks --watch` (only Backend/Frontend gate; wiki-drift + dep-audit are continue-on-error). Epic F9 → done.

## Risks
Interview gate waived by directive — 5 unvalidated bets may land as post-ship revisions. PRE-1 critic rejection stalls only A11yMenu/BookingCTA. `packages/ui` prop shapes become F10's contract. i18n extraction is the likeliest F7/F8 test breaker (convert one at a time). jsdom `<dialog>` partial — browser owns the real trap. Any `package.json` change stages the lockfile.

## Decisions (overridable)
Tokens single-source = theme.css + checked-in mirror + parity Vitest (no codegen). Optional `onSaved?` added to F7 sections (additive). Fonts via `@fontsource` deps in theme.css. `Modal` = native `<dialog>`. Playwright at `frontend/` root. `validation.ts` Hebrew stays hardcoded. PRE-1 geometric assertions split (console F9, storefront F10). ConsoleShell nav = plain nav + `aria-current`.
