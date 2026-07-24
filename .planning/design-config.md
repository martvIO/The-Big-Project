# Design Config — Bridal Boutique Platform

**Industry**: luxury bridal retail (Israeli market) · **Audiences**: brides (storefront, mobile-first) + boutique owners (manage console)
**Personality**: quiet luxury — warm, unhurried, editorial. Closer to a printed lookbook than a SaaS dashboard. Restraint over decoration; generous whitespace; photography does the talking.
**Anti-patterns (hard no)**: purple/blue SaaS gradients · neon accents · icon-per-feature clutter · Lorem/placeholder marketing fluff · gold text on cream (fails AA — see the gold law) · anything that reads "tech product" on the storefront.

## Binding sources
- Tokens: `.planning/design/system/tokens.md` (colors incl. the three-gold law, type, spacing, radius, shadows, motion)
- Components: `.planning/design/system/components.md`
- Screens: `.planning/design/screens/`

## Quick palette
cream `#FDFBF7` bg · paper `#F6F0E6` surface · ink `#2B2118` text · muted `#6B5D4F` · gold `#C5A059` (decor/CTA-bg only) · gold-strong `#9E7B36` (borders/large accents) · gold-text `#7F612B` (the only text gold) · success `#2E6B4F` · danger `#A03232`

## Fonts
Display: Frank Ruhl Libre (Hebrew serif — boutique names, headings). Body/UI: Assistant. Self-hosted via @fontsource. Hebrew default `dir="rtl"`; digits/prices always in body font.

## Language & locale
Hebrew-first, i18next-keyed from day one (Arabic arrives E10). Israeli week (Sun–Thu, short Friday). Currency ₪, amounts stored in agorot.

## Legal
IS 5568 / WCAG 2.0 AA is a legal requirement: contrast per tokens, visible focus, keyboard paths, labels, alt text, reduced motion, `/accessibility` statement page on every storefront.

## AI Asset Generation
Not configured (no GEMINI_API_KEY). Prototypes use CSS/SVG placeholder art; production imagery is tenant photography — upload guidelines live in the F8 handoff.
