# Spec: Feature 14 — Storefront Booking UI (Epic E3)

**Created**: 2026-07-29 · **Status**: DRAFT — Gate 1 not held · **Epic**: E3 Feature 14 · **Effort**: L (revised up from M — see §Scope correction)
**Depends on**: E3 #13 (the booking API), #12 (slots + appointment types), #11 (OTP send/verify), E2 #10 (the storefront app and its CTA seam), #9 (`packages/ui`) · **Feeds**: #16 (comms lifecycle sends against bookings created here), E4 (deposit redirect inserts into this flow)

> **This document is a draft written ahead of Gate 1, not an approved spec.** It was
> assembled from the shipped code and the approved roadmap, so the contracts and file
> paths are accurate. The product questions in **§Open questions** are deliberately
> left unanswered — they need a decision, and guessing them is how a spec becomes
> fiction. Nothing here should be built until those are settled.

## Problem

F13 shipped the endpoint that writes a booking. Nothing calls it. The storefront's
"קביעת תור" button has been live since F10, and it opens a contact panel — a real,
shipped fallback that tells the bride to phone the boutique. Every booking the pilot
takes today is still a phone call someone has to answer.

This is also the feature where the product's whole promise gets tested by a real
person: a bride on a phone, in Hebrew, right-to-left, who has to pick a time, prove
her number over SMS, read a cancellation policy and commit — without a single dead end
that leaves her not knowing whether she has an appointment.

## Scope correction — this is not a UI-only feature

The epic brief describes F14 as "the customer-facing flow ... on the storefront",
implying frontend only. It cannot be built that way, for a reason no earlier feature
surfaced:

**`POST /storefront/bookings` requires `terms_version`, and there is no public way to
learn it.** Terms live at `GET /manage/terms`, behind owner authentication. An
anonymous bride can neither discover the current version number to send nor read the
policy text she is being asked to accept. F13 rejects a stale or absent version with
`409 TERMS_STALE`, so without a public endpoint the flow cannot succeed even once.

F14 therefore carries a backend amendment. This follows F10's precedent exactly — that
spec has a section titled "The F7 profile amendment (delivered here, deliberately)" for
the same shape of problem — and the effort estimate moves M → L to match.

### The terms amendment (delivered here, deliberately)

`GET /storefront/terms` on the existing GET-only public router
(`backend/app/storefront/router.py`), anonymous, tenant-from-Host, `no-store` like
every sibling.

```json
{ "version": 3, "terms_text": "…", "refundable_until_hours_before": 48, "forfeit_percent": 50 }
```

**A strict field allowlist, per F10's "what the storefront must never see" rule.**
`TermsVersion` also carries `id`, `tenant_id`, `created_by` (the owner's staff UUID)
and the standard timestamps. None of those reach the anonymous wire; `created_by`
especially is an internal principal identifier with no business on a public surface.
The response object is built field-by-field, never by serialising the row.

`refundable_until_hours_before` and `forfeit_percent` ship alongside the text because
they are the two numbers a bride is actually agreeing to, and the UI should state them
in plain Hebrew rather than making her infer them from a paragraph.

**A boutique with no terms cannot take bookings** — F13 already enforces this, and the
manage console already treats it as a blocking banner ("אין מדיניות ביטולים",
`.planning/design/ideation/flows.md:43`). See **Q5** for what this endpoint answers in
that state.

## Goal

A bride reaches the storefront from an Instagram link, taps "קביעת תור", picks a real
bookable time, verifies her phone with a one-shot code, accepts the versioned policy,
and lands on a confirmation screen naming her appointment — in Hebrew RTL, on a 375px
screen, passing axe at WCAG 2.0 AA. Both paths work: from a dress page the booking
carries that dress and size; from the catalog or About it is a generic appointment.

Every failure the API can return has a designed recovery that keeps her in the flow —
in particular the two that happen to real people at real boutiques: the slot was taken
while she was typing, and the owner republished the terms mid-session.

## The contract F14 consumes (all shipped, verified against code)

Wire format is the backend's `snake_case` **verbatim** — the storefront does no case
conversion, and its TypeScript interfaces mirror the Python schemas field-for-field.
(`frontend/apps/storefront/src/api.ts` is the existing precedent; the `keysToSnake`
convention in `.claude/rules/` belongs to a different stack and does not apply here.)

| Call | Shape |
|---|---|
| `GET /storefront/appointment-types` | `[{id, name, duration_minutes, audience, deposit_required, deposit_amount_agorot}]` |
| `GET /storefront/slots?from=&to=` | `{slots: [{starts_at}]}` — bare instants; capacity is deliberately never on the wire. `from` defaults to today in Jerusalem, `to` to +14d, clamped to 60d; `to < from` is a 400 |
| `GET /storefront/terms` | **new, this feature** |
| `POST /storefront/otp/send` | `{phone}` → `204`. Always 204 — never reveals whether a code went out |
| `POST /storefront/otp/verify` | `{phone, code}` → `{verification_token, expires_at}` |
| `POST /storefront/bookings` | `{phone, verification_token, name, appointment_type_id, starts_at, terms_version, dress_id?, dress_size?, notes?}` → `201 {id, starts_at, status, appointment_type_name, dress_name, dress_size}` |

**Error codes the UI must map to Hebrew copy** (the house helper selects copy by
`code`, never by the server's message — every backend message is English):

| Code | Status | Meaning for the bride |
|---|---|---|
| `OTP_INVALID` / `OTP_EXPIRED` | 400 | wrong or stale code — retry inline |
| `PHONE_NOT_VERIFIED` | 403 | the token died (600s TTL) or was already spent — restart verification |
| `SLOT_UNAVAILABLE` | 409 | taken, off-grid, past, or beyond the published window — **re-fetch slots and re-pick** |
| `TERMS_STALE` | 409 | policy changed mid-session — **re-show and re-accept** |
| `NOT_FOUND` | 404 | the dress or appointment type was archived mid-session |
| `TOO_MANY_ATTEMPTS` | 429 | per-phone or per-tenant budget spent |
| `SMS_NOT_CONFIGURED` / `SMS_UNAVAILABLE` | 503 | phone verification is down — the flow cannot complete; say so honestly |
| `VALIDATION_ERROR` | 400 | shape violation; should be unreachable if client validation mirrors the server |

**The verification token's 600-second TTL is the flow's hard constraint.** It is minted
at `/otp/verify` and burned by `POST /bookings`. Everything between those two calls has
to fit inside ten minutes, which is what makes step ordering (**Q2**) a correctness
question rather than a taste one.

## What already exists to build on

- **The seam.** `frontend/apps/storefront/src/components/BookingCTAButton.tsx` is
  documented as "The E3 seam", with "E3 #14 replaces the panel's contents behind the
  same button". The button, its keyboard reachability and the fixed-bar footprint are
  shipped and QA'd.
- **`packages/api-client` is owned by this feature.** Its entire body is `export {}`
  plus a comment naming **"OWNER: E3 #14"** — the booking flow adds the first real
  request bodies, which is where codegen starts paying for itself, and hoisting the
  duplicated fetch helpers out of `apps/manage` and `apps/storefront` belongs in the
  same pass. `openapi-typescript` is already a devDependency with a `generate` script.
- **`apiFetch` is GET-only.** `frontend/apps/storefront/src/api.ts` takes no `init`,
  no method and no body. `frontend/apps/manage/src/api.ts` is the mutation-capable
  precedent — same `ApiError`/`extractError`, plus `{method, body}`. Note the
  storefront must keep `credentials: "omit"`: the booking route is cookie-blind by
  contract and a test asserts an owner cookie changes nothing.
- **i18n.** `frontend/apps/storefront/src/i18n/he.ts` already has a `booking` section
  (`cta`, `panelTitle`, `close`). Every visible string must live there — no component
  may hardcode Hebrew — and `__tests__/i18n-keys.test.ts` statically enforces it for
  any new `booking.*` key automatically.
- **Layout.** `StorefrontLayout` owns the single app-wide boutique fetch, `#content`
  focus management, and `hasBookingBar(route)` — a hardcoded
  `route.name === "catalog" || route.name === "dress"` switch that a new booking route
  must be added to or deliberately excluded from.

### What `packages/ui` does not have

Every one of these is needed by a booking flow and absent today, so each is either a
new component in `packages/ui` or a deliberate one-off in the app:

stepper / progress indicator · radio group · checkbox (needed for terms acceptance) ·
chip or segmented control · any date picker or calendar (only native
`<input type=date>`) · slot grid · OTP code input · phone input forced LTR ·
form/fieldset wrapper · form-level error summary · client validation utilities
(`apps/manage/src/validation.ts` is the precedent: pure functions returning a Hebrew
string or `null`).

Three existing constraints will bite:

1. **`Modal` is fixed-width (`w-[min(28rem,…)]`) with no scroll handling and no size
   variants.** A multi-step form with a slot grid and a policy text does not fit it as
   built. This is the strongest argument for **Q1** resolving toward a route.
2. **`cn` has no tailwind-merge**, so caller classNames cannot reliably override a
   component's base classes — which rule wins is decided by stylesheet order.
   `BookingCTAButton` documents being bitten by exactly this.
3. **Toast is one-at-a-time with no queue**, 4s auto-dismiss. It cannot carry anything
   the bride must read, and must not be the only report of a failure.

## Open questions — Gate 1 must answer these

**Q1 — Route or modal?** The codebase contains two hints pointing opposite ways.
`BookingCTAButton`'s docstring says F14 "replaces the panel's contents behind the same
button" (a modal). `router.tsx`'s header names `matchRoute` as the seam for adopting
react-router when **"E3's booking flow needs nested layouts"** (a route). They cannot
both be honoured. A route gives back-button semantics, a shareable/recoverable URL, and
room the fixed-width `Modal` does not have; a modal preserves the shipped CTA behaviour
and touches less. *Recommendation: a route (`/book`, optionally `/book?dress=…`), with
the CTA navigating instead of opening the panel — but this changes shipped, QA'd
behaviour and is the single biggest structural call in the feature.*

**Q2 — Step order, against the 600-second token.** The brief says "slot picker, details
+ OTP verification step, terms checkbox, confirmation". Verification must sit as late
as possible or the token expires while she reads the policy. *Recommendation: slot →
details (name, optional notes) → terms acceptance → OTP → submit, so the code is the
last thing before commit. Needs confirmation because it puts the policy before the
identity check.*

**Q3 — Deposit-required appointment types, with E4 unbuilt.** `/appointment-types`
exposes `deposit_required` and `deposit_amount_agorot`, but no payment exists. Today a
bride booking such a type confirms instantly and pays nothing — the boutique's deposit
policy silently does not apply. Hide those types until E4, show them disabled with an
explanation, or accept free bookings for the pilot? **This is a business decision with
revenue consequences and I should not pick it.**

**Q4 — Can she book a size marked unavailable?** `SizeChip.available` is `quantity > 0`,
and F13 validates only that the variant *exists and is active*, not that it is in
stock. A bride may legitimately want to try a size the boutique must order in.
*Recommendation: allow it, since a fitting is not a purchase — but say so in the UI.*

**Q5 — What does `GET /storefront/terms` answer when a boutique has no terms?**
`404 NOT_FOUND` (house shape, consistent with every other absent resource) or `200`
with a null body? Either way the booking entry point must degrade to the shipped
contact panel rather than a broken form. *Recommendation: 404, and the CTA falls back.*

**Q6 — Does the confirmation screen promise an SMS?** It must not: **F16 has not
shipped, so a booking created here sends nothing.** Until then this screen is the only
confirmation that exists, which raises its stakes considerably — it may need to tell
her to screenshot it. If F16 lands first, this copy changes.

**Q7 — Is `notes` in the v1 form?** It is the first customer-authored free text in the
product. F13 bounds it at 500 chars and strips control characters, and F15 must render
it as text and never HTML.

## Out of scope

The manage/cancel link and every SMS send (F16) · owner-side views of these bookings
(F15) · deposits and the payment redirect (E4) · waitlist (E5) · a client dashboard or
login (E5) · `.ics` download (E5) · calendar-grid slot visualisation (E10).

## Testing

**Unit (Vitest + Testing Library, `src/__tests__/`, `TZ=America/New_York` pinned).**
Model on `CatalogPage.test.tsx`: `vi.mock("../api")` spreading `importActual` so
`ApiError`/`errorMessage*` keep real behaviour, render inside the real
`StorefrontLayout`, assert against real Hebrew strings from `i18n`. Cover each step's
validation, every error code's recovery path, the token-expiry path, and the two
mid-flow conflicts (`SLOT_UNAVAILABLE` re-pick, `TERMS_STALE` re-accept).

**Backend (pytest).** The new terms endpoint needs the house treatment: field-allowlist
assertion (`created_by` and `tenant_id` must be absent from the response), the
no-terms state, cross-tenant isolation, `no-store`, cookie-blindness, and its row in
`test_storefront_api.py`'s cross-router shadowing guard.

**E2E (Playwright, `frontend/e2e/storefront.spec.ts`).** Fixture-driven route
interception like the existing specs; add booking fixtures and an axe pass per new
route with `withTags(["wcag2a","wcag2aa"])`. Plus the standing route checks: no
horizontal scroll at 375/768/1440, skip link first Tab stop, reduced-motion honoured.

**Mechanical.** `frontend/scripts/qa-greps.sh` fails on physical-direction classes
(`ml-`, `pl-`, `left-`, `text-left`, …), raw hex colours, `₪`, and `localStorage` —
the booking form must use logical properties throughout, and Latin/numeric runs (phone
numbers, times, the OTP field) need `<bdi dir="ltr">` per the existing bidi precedent.

## Dependencies

F13, F12, F11, F10, F9 — all merged. **A design gate is required**: no booking screens
exist in `.planning/design/screens/`, and CLAUDE.md makes a design doc non-optional for
new frontend screens. `/spartan:ux prototype` should produce
`.planning/design/screens/booking/` before implementation planning, and it must design
all states (loading, empty, error, success, and the two mid-flow conflicts) per the
design-process rules.

## Risks

1. **The token TTL crossed with a slow reader.** Ten minutes is generous for a form and
   short for someone reading a cancellation policy on a phone. If Q2 puts terms before
   OTP this is handled; if not, expect real `PHONE_NOT_VERIFIED` failures on the
   happy path.
2. **Silence after success.** Until F16, a confirmed booking produces no SMS. The
   ordering is deliberate and recorded in F13's spec, but F14 is where a real customer
   first feels it.
3. **Adopting codegen and shipping a flow in one feature.** The `api-client` OWNER note
   assigns both here. If codegen adoption proves noisy it should be split into its own
   PR ahead of the flow rather than blocking it.
4. **`hasBookingBar` and the fixed CTA bar.** A booking route that keeps the bar would
   show a "book" CTA inside the booking flow. Easy to miss, and qa-checklist §7 has
   opinions about that bar at every width.

## Decisions log

*(empty — this draft has made no decisions. Q1–Q7 are open.)*
