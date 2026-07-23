# Flows & Information Architecture — v1 surfaces

**Created**: 2026-07-22 · **Feeds**: system tokens (Phase 4), screen designs (Phase 5) · **Booking flow itself is E3 F14** — here it exists only as a CTA seam.

## Information architecture — tenant subdomain `{slug}.<domain>`

```
{slug}.<domain>/
├── /                     Storefront home = catalog grid + boutique header (v1: one page, no separate home)
├── /dress/{id}           Dress detail
├── /about                Boutique profile: story, contact, hours, map link  (may fold into / footer-section in v1 — decided at prototype)
├── /accessibility        הצהרת נגישות — IS 5568 statement page (legal requirement)
└── /manage/…             Owner console (F7, auth-gated): Profile & toggles · Hours & exceptions · Appointment types · Cancellation policy  (+ F8 Catalog later)
```

Navigation model: storefront is deliberately shallow — brides arrive from Instagram/WhatsApp links and must reach a dress or the booking CTA in ≤2 taps. No mega-nav, no hamburger labyrinth.

## Flow S1 — Bride browses the catalog (mobile-first)

**Entry**: Instagram bio link / shared WhatsApp link / Google → lands on `/`.

1. Sees boutique identity header (name, one-line essence, location + hours snippet) over the catalog grid → *instant "is this my style/level" read*.
2. Scrolls grid: dress cards (photo-dominant, name, price or "מחיר בתיאום" per visibility flag, status badge only when meaningful — e.g. הוזמן).
3. Taps a dress → **S2**.
4. Sticky/persistent **"קביעת תור" CTA** (grid + detail) → E3 booking flow (v1 stub: opens contact panel — phone/WhatsApp deep-link — honest fallback until E3 ships).

**Error/edge paths**: empty catalog → dignified empty state (boutique identity + hours + booking CTA still work — the storefront must be useful pre-catalog since F7 ships before F8) · price-hidden dresses → "מחיר בתיאום" style treatment, never a broken gap · suspended tenant → platform 404 (F4 behavior, not a design surface) · slow network → skeleton grid.

## Flow S2 — Dress detail

1. Gallery (swipe on mobile, thumbs on desktop; 3:4 portrait ratio locked — survives mediocre photography via consistent crop + cream matting).
2. Name · price (or discreet "מחיר בתיאום") · status · description · size/variant availability presented as informational chips (no cart — this is book-to-try, not e-commerce).
3. Primary CTA "קביעת תור למדידה" → booking seam. Secondary: back to catalog (breadcrumb, RTL-correct), share.
4. Edge: single-photo dress (gallery degrades gracefully) · long description (clamp + expand) · archived dress reached via old link → "לא זמין יותר" state with CTA to catalog.

## Flow S3 — Bride vets the boutique (trust loop)

From grid or detail → profile section/page: story text, phone (tap-to-call), WhatsApp link, address with maps deep-link, this week's hours (Israeli week Sun–Thu + Fri short, "סגור" days explicit, exceptions surfaced as "שעות מיוחדות"), Instagram link. Trust artifacts: real address + live hours + coherent photography ≫ badges.

## Flow M1 — Owner configures the boutique (F7 restyle)

Login (`LoginForm`) → console shell with four sections (Profile & toggles / Hours & exceptions / Appointment types / Cancellation policy).
- First-run state: checklist-style progress ("3/4 הושלמו") pointing at the next unconfigured section; **"אין מדיניות ביטולים" is a blocking banner** (E3 requires an active terms version for any booking).
- Steady state: sections are forms with explicit save, optimistic error recovery (house error shape), and visible "last saved" cues.
- Restyle constraint: structure/behavior of the five F7 components is already built and tested — the restyle changes tokens, spacing, typography, and states' visual language, not the component API.

## Flow M2 — Owner maintains hours & policy (recurring)

Exception dates for holidays (add/remove, closed vs special hours) · new terms version when policy changes (immutable history visible — "גרסה 3 · נוצרה 12.3" list) · appointment types toggled/archived seasonally. Design must make the *irreversibility* of terms versions legible (create-only form + history, no edit affordance).

## Key screens (→ Phase 5)

1. **Storefront catalog** (`/`) — grid + identity header + CTA. States: default, loading (skeleton), empty (pre-F8), price-hidden mix.
2. **Dress detail** (`/dress/{id}`) — gallery + facts + CTA. States: default, single-photo, archived, loading.
3. **Profile & hours** (`/about` or section) — trust surface. States: default, no-exceptions, closed-today.
4. **Manage restyle** — console shell + the five F7 components restyled; first-run checklist + policy-blocker states.

## Data relationships already fixed by backend (design consumes, not invents)

Boutique profile/toggles = `tenants.settings` (F7) · hours = `availability_rules` + `availability_exceptions` (F7) · types/deposits = `appointment_types` (F7) · policy = `terms_versions` (F7, immutable) · dresses/variants/media = F8 tables (grid designs against this shape) · price visibility = per-dress flag (F8).
