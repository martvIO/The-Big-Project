# Epic: E2 — Boutique Setup & Catalog

**Created**: 2026-07-21 (rev 2 — post verification pass)
**Status**: planning
**Owner**: team
**PRD**: §2 (owner controls), §3 (inventory), storefront browse half of §4

---

## Why

Before anyone can book, the boutique must exist as a configured business (hours, appointment types, cancellation policy, toggles) with a catalog worth browsing. This epic delivers the owner's setup surfaces, the brand-defining design system (with its design gate), and the public storefront in browse-only form — the booking flow itself is E3. Verification pass split design system from storefront and made the cancellation policy machine-readable (E4's refund/forfeit logic depends on it).

---

## Success Criteria

- [ ] Owner configures hours + exceptions, appointment types (duration, audience, deposit amount), and a **versioned cancellation policy combining terms text + structured refund-window fields**; v1 toggles work (deposit on/off, brides-only, price visibility per item)
- [ ] Owner manages dresses with size/qty variants, status (available / out-of-stock / manual reserved flag), and multi-image galleries via presigned S3 upload
- [ ] Customers browse the catalog and dress pages on the tenant subdomain in Hebrew RTL, luxury cream/gold design, WCAG 2.0 AA (IS 5568), price visibility respected

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 7 | Owner settings, toggles & structured cancellation policy | building | [spec](../specs/owner-settings.md) | [plan](../plans/owner-settings.md) | E1 #5 |
| 8 | Catalog management | todo | — | — | E1 #2 (S3 base), E1 #5 |
| 9 | RTL design system & tokens | spec | [design package](../design/screens/design-system/README.md) | — (build plan after interview-gated final approval) | E1 #1 |
| 10 | Storefront browse | todo | — | — | E1 #4, #7, #8, #9 |

---

## Feature Briefs

### Feature 7: Owner settings, toggles & structured cancellation policy (M)
Boutique profile, weekly opening hours + exception dates (Israeli week: Sun–Thu, short Friday, holidays), appointment types (name, duration, audience brides-only/all, deposit required + amount), and the v1 subset of the §2 toggle matrix. **Cancellation policy = free-text terms PLUS structured fields (refundable-until-hours-before-appointment, forfeit rule), versioned immutably together** — the structured fields are what E4 Feature 19 evaluates; the text is what the customer accepts (evidence for forfeiture + PPL). Tables: `appointment_types`, `availability_rules`, `terms_versions`, settings JSONB.

### Feature 8: Catalog management (M)
Dress CRUD (name, description, price, price-visibility flag, status), size/quantity variant matrix, multi-image upload via presigned S3 (tenant-prefixed keys, content-type/size validation — **consumes the bucket provisioned by E1 Feature 2**; upload config lands here, gated on AWS-account approval), gallery ordering. Owner UI in `apps/manage`. Video reels are E10. **"Reserved" is a manual, date-less owner flag in v1; date-bound reservation semantics (מוזמן לתאריך מסוים) are explicitly deferred to E5 #7**, pending the pilot's purchase/rental/made-to-order answer.

### Feature 9: RTL design system & tokens (M)
`packages/ui`: cream/gold token system, RTL-first components (CSS logical properties), typography, luxury motion language. **Design gate via `/spartan:ux prototype` happens here** — including resolving the AA-contrast problem (raw #D4AF37 gold on cream fails for text; gold becomes accent, darker ink carries text). Depends only on the repo scaffold, so it runs in parallel with E1's backend features.

### Feature 10: Storefront browse (M)
`apps/storefront` on the tenant subdomain: catalog grid + dress detail pages, Hebrew, i18next-keyed from day one, price visibility and boutique profile (name, contact, hours) rendered from Feature 7 data. Booking CTAs appear but the flow lands in E3 Feature 14.

---

## Risks

- Design gate (Feature 9) is a serialization point for Feature 10 — schedule it early; backend features 7–8 proceed in parallel.
- Catalog photography quality is outside our control but defines the "luxury" perception — give the pilot upload guidelines.

## Notes

- Features 7, 8, 9 are mutually independent and parallelizable; 10 is the join point.
