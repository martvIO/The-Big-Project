# Design Gate Package — F9 rev 2 · **GATE: PASSED (design-critic ACCEPT, round 2)**

**Screens**: `storefront-catalog.md` · `storefront-dress-detail.md` · `storefront-profile-hours.md` · `manage-restyle.md` · **Prototype**: `prototype.html` (self-contained RTL; fonts via Google Fonts link for preview only — production self-hosts)
**Gate**: design-critic agent, max 3 rounds. FINAL approval follows interview synthesis (`../../research/interview-status.md`).

**Gate log**: Round 2 — **ACCEPT** (all 16 round-1 findings verified fixed in code; 5 residual minor/nits applied post-accept: CSS-comment syntax in `.fav-slot`, `aria-hidden` on `.monogram`, tokenized `.skip`/`.a11y-btn` px values; error-block-identity and hours-card closed-today variants noted for F9 build QA). **FINAL approval still gates on interview synthesis.** · Round 1 — NEEDS CHANGES (16 findings: missing skip-link + statement-link coverage [blockers]; aria-describedby wiring, a11y-btn touch target, off-scale type sizes, missing detail mobile CTA bar, physical `text-align:left`, no loading/error states rendered, CTA-bar responsive behavior [majors]; token/radius/dir/contrast-table minors). All applied in prototype rev 2 + tokens/spec updates: per-screen skip-links, statement footer on every storefront screen, `--t-*` scale enforced, `.num-col{text-align:end}`, states screen added (skeleton/error/monogram/closed-today), CTA header-inline @≥768 + bottom bar mobile-only, illustration fills tokenized, warning-on-paper contrast computed (5.20:1).

## Motion plan (shared)

| Element | Animation | Trigger | Duration/Ease |
|---|---|---|---|
| Page content | fade + 8px rise | route/section change | 200ms ease-out |
| Modal | scale 0.97→1 + fade; backdrop fade | open | 200ms / 150ms |
| Toast | slide from block-start + fade | show | 300ms |
| Grid images | fade-in on load | img load | 200ms |
| Skeleton | pulse | loading | 1.5s loop |
| Gallery | swipe follows finger; snap | drag | native scroll-snap |

`prefers-reduced-motion: reduce` ⇒ all transitions none, skeleton static, scroll-snap retained (it's navigation, not decoration).

## Accessibility checklist (IS 5568 / WCAG 2.0 AA — checked at gate AND at build QA)

- [x] Contrast: every text pair from tokens ≥4.5:1 (computed, see tokens.md); non-text UI boundaries ≥3:1 (`gold-strong`, `border-input`)
- [x] Gold never carries text except `--color-gold-text`
- [x] Keyboard: all interactive elements reachable; skip-link on storefront; focus order = visual order (RTL-aware)
- [x] Focus visible: 2px `--color-focus` ring, 2px offset, never removed
- [x] Labels: every input has a visible label; errors tied via `aria-describedby`
- [x] Images: dress photos get alt from dress name; decorative ornaments `aria-hidden`
- [x] No color-only signals (status = badge text; exceptions = marker + text)
- [x] Touch targets ≥44×44 @mobile (CTA bar 56px)
- [x] Reduced motion honored
- [x] `/accessibility` statement page (הצהרת נגישות) linked in storefront footer — content template lands in the F9 build
- [x] `lang="he" dir="rtl"` document-level; LTR islands for phone/URL/digits
