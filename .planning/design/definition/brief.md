# Design Brief — Bridal Boutique Platform (v1 surfaces)

**Created**: 2026-07-22 · **Status**: provisional — personas/journeys pending interview validation (`../research/interview-status.md`) · **Sources**: PRD via epics E1–E4, `.planning/architecture.md`, competitive research (`../research/`)

## Problem statement

**Brides** need to judge — from their phone, usually at night — whether a boutique is worth one of their few precious fitting visits, because today boutiques exist online as Instagram grids and WhatsApp threads with no prices, no availability, and no way to book without a multi-message negotiation.

**Boutique owners** need bookings to arrive confirmed, deposit-backed, and on calendar without them being the switchboard, because today every appointment costs a WhatsApp conversation, and a no-show costs a fitting room, a stylist, and an afternoon.

## Personas (2 — provisional)

### Noa, 28 — the bride
**Goal**: find *the* dress within budget, in ≤4 boutique visits, before the dress deadline (~6 months pre-wedding).
**Behavior**: researches on her phone in the evening; discovery starts on Instagram and ends in WhatsApp; keeps a shortlist in screenshots; drags her mother/sister into every decision.
**Frustration**: no prices anywhere ("אם צריך לשאול — כנראה יקר מדי"), no idea if a boutique fits her budget until she's already there; booking takes a day of message ping-pong.
**Trigger**: a friend's recommendation or an Instagram post → she wants to vet the boutique NOW, at 23:00.
**Success looks like**: in two minutes on her phone she sees the collection, a price range, real photos, where the boutique is, and books a Saturday-night-visible slot — without talking to anyone.

### Rivka, 45 — the boutique owner
**Goal**: full fitting rooms, zero no-shows, and evenings that end when the boutique closes.
**Behavior**: runs the boutique's Instagram herself; manages appointments in WhatsApp + a paper diary/Google Calendar; answers the same five questions ("כמה עולה?", "איפה אתן?", "יש תור ביום שישי?") dozens of times a week.
**Frustration**: no-shows on peak Fridays; price hagglers; being unreachable during fittings means lost bookings; "טכנולוגיה" that requires a manual.
**Trigger**: a no-show week or a competitor's slicker online presence.
**Success looks like**: bookings appear confirmed (deposit-backed when she wants), her policies enforce themselves, and the storefront makes her boutique look like the luxury business she runs.

## Journey — bride books a fitting (current state, pre-platform)

| Stage | Action | Thinking | Feeling | Pain (severity) |
|---|---|---|---|---|
| Discover | Instagram hashtags, friends, גוגל "שמלות כלה + עיר" | "Which of these is my style? My budget?" | excited, overwhelmed | No comparable info between boutiques (M) |
| Research | Scrolls boutique IG, hunts for prices, checks location | "Can I afford this place? Is it real?" | anxious | Prices hidden; no address/hours; dated or no website (H) |
| Contact | DMs/WhatsApps the boutique | "Hope they answer before I lose interest" | impatient | Reply latency: hours–days; asymmetric info exchange (H) |
| Book | Negotiates a slot over messages | "Is it actually confirmed?" | uncertain | 10–20 messages per booking; no confirmation artifact (H) |
| Wait | Screenshot of a chat as her "ticket" | "When was it again?" | forgetful | No reminders → no-shows (M, owner-side H) |
| Visit | Arrives; sometimes the slot was double-booked | "Did they expect me?" | delighted or burned | Double-booking, no prep info (M) |

## Journey — owner sets up & operates (current state)

| Stage | Action | Pain (severity) |
|---|---|---|
| Present | Maintains IG; maybe a stale website | Looks less premium than the gowns; no structured catalog (M) |
| Intake | Answers every inquiry personally | Switchboard tax: hours/week on 5 repeated questions (H) |
| Schedule | Paper/GCal/WhatsApp triangulation | Double-bookings; peak-day chaos (H) |
| Protect | Asks for deposit ad-hoc, awkwardly | Inconsistent; arguments; some just skip it and eat no-shows (H) |
| Operate | Reschedules/cancels by phone | Every change is another conversation (M) |

## Success metrics

| Metric | Current | Target (pilot) | Measure |
|---|---|---|---|
| Bride: storefront visit → booking CTA tap | n/a (no storefront) | ≥ 25% | analytics on CTA (E3+) |
| Bride: time from landing → confirmed booking | ~1 day (WhatsApp) | < 3 min (E3) | funnel timing |
| Owner: full setup (profile+hours+types+policy) unaided | n/a | < 30 min, zero support calls | pilot onboarding observation |
| A11y: IS 5568 / WCAG 2.0 AA audit | n/a | pass (axe-core + manual) | E4 #21 audit |
| Mobile: storefront usable at 375px on 3G-class | n/a | LCP < 2.5s, no horizontal scroll | Lighthouse |

## Scope

**IN (this design phase)**: design tokens + component system (`packages/ui`) · storefront catalog grid, dress detail, boutique profile/hours · restyle spec for the five F7 manage components · booking CTA presence (stub — flow is E3).
**OUT (later)**: booking flow screens (E3 F14) · client dashboard (E5) · waitlist (E5) · video reels (E10) · Arabic storefront (E10) · self-serve signup (E5).
**Hard constraints**: Hebrew RTL-first, CSS logical properties, i18next keys · IS 5568/WCAG 2.0 AA legal floor · cream/gold/ink luxury brand (gold never carries body text — AA) · 375/768/1440 breakpoints · per-dress price-visibility respected · photography is tenant-supplied (design must survive mediocre photos).
