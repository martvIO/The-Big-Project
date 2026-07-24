# Competitive Teardown — synthesis of the 5-lens research pass

**Created**: 2026-07-22 · **Method**: 5 parallel researchers over live sites (Israeli boutiques · global bridal leaders · booking platforms · RTL/luxury e-comm · IS 5568 practice). Full structured findings with per-site evidence live in the research-run archive; this file is the decision-grade summary.

## The market picture

| Segment | Examined | Verdict |
|---|---|---|
| Israeli boutiques (mid-tier) | mikabridal, noavayelet, helenakolan, jozefsiboni, kshoshana, svalentina, rinatshacham | Elementor/Wix template rot: placeholder text in production, year-folder "catalogs", CTA spam, WhatsApp as the only booking channel, percent-encoded Hebrew URLs, overlay-widget "accessibility" |
| Israeli/IL-founded luxury | Galia Lahav, Mira Zwillinger | Restraint + photography + whitespace; Galia's appointment form (wedding date, budget band, preferred channel) is the local luxury signal; proper Hebrew RTL mirroring |
| Global bridal leaders | Kleinfeld, Pronovias, Grace Loves Lace, BHLDN | Booking-is-the-conversion; structured dress attributes; typed appointment menus; portrait 3:4 imagery; no-login favorites (GLL) vs login-gated (Galia — friction) |
| Booking platforms | Fresha, Booksy, StyleSeat, Square | Venue-page anatomy (status line, hours, map, per-service book buttons); phone-first OTP identity; deposit-deducted-at-checkout model; merchant rage at fees/brand-hijack — our no-marketplace subdomain model attacks their weakest point |
| Israeli fashion e-comm (register reference) | Castro, Renuar, Terminal X, Adika, Factory 54, Karin Bar | Assistant + display-serif is the luxury stack (Factory 54, Karin Bar); sale-badge visual language is exactly what bridal must never use; shekel placement chaos proves the need for one enforced Price component |

## What wins by default (their failures → our features)

1. **Real slot booking does not exist locally.** Every boutique books via WhatsApp/phone. A first-class "קביעת תור" flow instantly outclasses the market — while coexisting with WhatsApp (wa.me secondary CTA, WhatsApp-shareable confirmations).
2. **Template rot is the norm** — placeholders, stale 2022 trunk-shows, dead DNS. A platform where empty/stale states are *unrenderable* (validated content, designed empty states, no announcements feature at all in v1) reads premium by construction.
3. **Mobile-first is claimed, never practiced.** Designing at 375px with a thumb-reach booking bar is the most visible premium signal available.
4. **Native accessibility beats the overlay widget.** Everyone ships a third-party נגישות widget over an inaccessible site; AA-by-construction + a first-party lightweight menu + auto-generated statement page is both compliant and visually cleaner.
5. **Restraint is the differentiator inside the cream/gold vocabulary.** Mid-tier adds ornament; Galia adds air. We add air.

## Patterns adopted into rev 1 (this pass)

Sticky bottom booking CTA @mobile, one conversion path per page · venue-page anatomy on the profile (status line "סגור — נפתח מחר ב-10:00", hours table, map/directions) · Waze + Google Maps one-tap links (Waze is culturally standard) · wa.me secondary CTA · portrait 3:4 enforced imagery · price visibility as per-boutique/per-dress strategy with "מחיר בתיאום" as the dignified hidden mode · Assistant body + Frank Ruhl Libre display (the Factory 54/Karin Bar stack family; Latin-only serifs like Playfair banned for Hebrew headings) · one enforced `Price` component, convention **"5,900 ₪"** with LTR isolation · first-party accessibility menu (bottom-left in RTL: contrast, text size, readable font, underline links, stop animations) · footer הצהרת נגישות link on every page.

## Deliberately NOT adopted (with reasons)

Filter-heavy catalogs (Kleinfeld's 12 dimensions suit 1,000 dresses, not 40 — F8/F10 get 3 facets max) · login-gated favorites (kills the feature) · consumer booking fees (StyleSeat's 1.5-star lesson) · platform-branded booking pages (Fresha's top merchant complaint — booking stays inside the boutique's brand) · announcements/promo slots (stale-content machine; sale-badge register) · third-party a11y overlay as compliance story · year-folder navigation · budget-band field forced on all tenants (optional per-boutique, per Galia's form).
