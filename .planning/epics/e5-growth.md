# Epic: E5 — Growth: Waitlist, Client Dashboard, Self-Serve Signup & Console

**Created**: 2026-07-29
**Status**: planning — **roadmap only, by the same decision that governs E4 (recorded 2026-07-29).** E5 is gated on E4: no E5 feature gets a spec until v1 has shipped through the Feature 21 gate. Each feature is spec'd feature-by-feature when its turn arrives, matching the per-feature `/spartan:spec` → `/spartan:plan` → `/spartan:build` pipeline every shipped feature has used. Defining the epic now records the feature split, the global renumbering, and the decisions v1 work has already forced on it.

**Numbering**: this file promotes the roadmap's E5-local stub (#1–#7) to the **global feature scheme (#22–#29)** used by e1–e4, and splits the old #4 bundle in two. Mapping: #1→#22, #2→#23, #3→#24, #4→#25+#26, #5→#27, #7→#28, #6→#29. All `E5 #N` cross-references in ROADMAP/e1–e4 are updated to the global numbers.
**Owner**: team
**PRD**: §6 (waitlist + auto-reallocation loop), §5 (client dashboard, `.ics`, refund automation), §2 (feature-toggle grid, self-serve signup & console)

---

## Why

v1 (E1–E4) proves one boutique end-to-end with an operator holding its hand; E5 turns that into a growth machine. Three thrusts: **recover lost demand** — a full day of booked slots currently turns brides away, so waitlist + race-safe auto-reallocation puts freed slots back to work; **give the customer a durable surface** — in v1 her only control is a tokenized SMS link, so the OTP dashboard, `.ics` links and notification bell make her a returning user; **remove the operator bottleneck** — the audited CLI (E1 #6) cannot onboard 50+ tenants, so the web console and self-serve signup replace it, gated behind the pre-scale hardening pass (#29) so public tenant creation never outruns the platform's load and abuse posture.

---

## Success Criteria

- [ ] A customer joins the waitlist from a fully-booked storefront day; when a slot frees, sequential offers cascade with expiry, and a claim is **atomic and race-safe against a concurrent direct booking** — proven by a concurrency test (same standard as E3 #13's double-book test)
- [ ] A customer logs in with **OTP only** (email login was dropped by recorded stakeholder decision), sees and manages her bookings, adds appointments to her calendar via `.ics` links (the recorded replacement for 2-way sync), and receives in-app bell notifications
- [ ] A new boutique goes from signup to live storefront with **zero operator involvement** — subdomain claimed (reserved slugs blocked), gateway connected via onboarding built on E4 #17 — and the operator manages tenants from the web console (v1 CLI retired); the signup goes public **only after #29 is green**
- [ ] The pre-scale gate holds: refunds execute via the Grow API (replacing E4's manual-console step), the k6 load pass that was deliberately cut from v1 is green, and slug/config lookups are cached in Redis **including a bounded negative-result cache** (E1 #4 security-review finding); the owner controls the full §2 toggle grid, and a dress can be reserved date-bound (מוזמן לתאריך מסוים) per the pilot's decided semantics

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 22 | Waitlist join + entries model | done (PR #49) | [spec](../specs/waitlist-join.md) | [plan](../plans/waitlist-join.md) | E3 #12, #13, #14 |
| 23 | Auto-reallocation loop | done (PR #56) | [spec](../specs/waitlist-auto-reallocation.md) | [plan](../plans/waitlist-auto-reallocation.md) | #22, E3 #16, E4 #19 |
| 24 | Client portal: OTP login, "My Bookings", `.ics`, bell | done (PR #50) | [spec](../specs/client-portal.md) | [plan](../plans/client-portal.md) | E3 #11, #13, #16 |
| 25 | Web platform console (replaces v1 CLI) | done (PR #52) | [spec](../specs/platform-console.md) | [plan](../plans/platform-console.md) | E1 #6 |
| 26 | Self-serve boutique signup + gateway-connect onboarding | todo | — | — | #25, E1 #4, E4 #17 · **public launch gated by #29** |
| 27 | Full feature-toggle matrix UI (§2 grid) | done (PR #51) | [spec](../specs/toggle-matrix-ui.md) | [plan](../plans/toggle-matrix-ui.md) | E2 #7 |
| 28 | Date-bound dress reservation semantics | done (PR #53) | [spec](../specs/dress-reservation.md) | [plan](../plans/dress-reservation.md) | E2 #8, E3 #13 · Q9 settled it: RENTAL |
| 29 | Pre-scale gate: refund-API automation, k6, Redis caching | todo | — | — | E4 #18, #21 |

**Sequencing when E5 starts**: #22 → #23 are a chain and the epic's transactional heart — spec them first. #24 is independent of the waitlist chain and can run in parallel. #25 → #26 are a chain; #26 can be *built* early but its **public launch is gated by #29** — a platform that invites the public to create tenants must already have its load pass, caching, and automated refunds. #27 is small and slots anywhere after E2 #7. #28 waits on the pilot's purchase/rental/made-to-order answer — if that decision is still open when E5 starts, everything else proceeds around it.

---

## Feature Briefs

### Feature 22: Waitlist join + entries model (M)
Storefront waitlist join on the full-day path: when a day shows no availability, the customer (OTP-verified phone, same E3 #11 primitive the booking flow uses) joins a tenant-scoped `waitlist_entries` model bound to day + appointment type. Owner sees entries in `/manage`. Deliberately kept out of E3 (recorded note there): it needs the booking core live first.

### Feature 23: Auto-reallocation loop (L)
When a slot frees (cancellation, expired hold), offer it to waitlist entries **sequentially with an expiry cascade** — each offer is a tokenized SMS (E3 #16 infrastructure) with a claim deadline; expiry advances to the next entry. Claim is an **atomic conditional update protected by the same partial-unique-index structure as direct booking** — the race-safe offer/claim design is already spec'd in the pressure-test plan (`architecture.md`). Hardest spec question, decided at spec time: the **deposit interplay** — a claim on a deposit-on appointment type must enter E4 #19's `pending_payment` hold with its own expiry, and an expired claim-hold re-fires the cascade, race-tested like E4 #19's hold-expiry-vs-late-webhook.

### Feature 24: Client portal: OTP login, "My Bookings" dashboard, `.ics` links, client bell (L)
Customer logs in on the tenant storefront via the E3 #11 OTP primitive — **OTP-only; email verification was dropped by recorded stakeholder decision**. Dashboard lists her bookings with the same manage/cancel actions as the tokenized link (which remains valid for non-login users). Per-booking `.ics` download/link — the recorded replacement for 2-way Google/Apple calendar sync. **Client-side notification bell** (booking confirmed/changed/reminder): E5 predates E6's Pusher foundation, so the bell is poll-based in this epic — the delivery substrate question is settled at spec time. E9's multi-fitting scheduling builds on this feature's dashboard + `.ics`; E6 #5's staff bell mirrors it (different substrate — Pusher, not polling), with no dependency between them.

### Feature 25: Web platform console (M)
Operator-facing web console replacing the v1 CLI (E1 #6): provision/suspend/list tenants, reset owner passwords — same operations, same audit-log obligation, now with a UI that scales past pilot-cohort onboarding. The CLI's audited command layer becomes the console's service layer; the CLI itself is retired once the console reaches parity.

### Feature 26: Self-serve boutique signup + gateway-connect onboarding (M)
Owner-facing public signup: claim a subdomain (validated against E1 #4's reserved-slug list), create the boutique + first owner login through the same provisioning path the console uses, then a **gateway-connect onboarding step** wrapping E4 #17's credential management + validation ping so a new tenant can take deposits from day one. Opens tenant creation to the public — abuse surface (slug squatting, junk tenants, rate limits) is first-class spec scope, and **the feature does not launch publicly until #29 is green**.

### Feature 27: Full feature-toggle matrix UI (S)
Expands E2 #7's v1 subset of the §2 toggle grid into the complete matrix in owner settings, with per-feature enable/disable persisted in tenant settings JSONB. Small by design; grows a row whenever a later epic ships a toggleable feature.

### Feature 28: Date-bound dress reservation semantics (M)
The owning feature for מוזמן לתאריך מסוים: E2 #8 shipped "Reserved" as a manual, date-less owner flag, explicitly deferring date-bound semantics here, **pending the pilot's purchase/rental/made-to-order answer** (open product question recorded in the roadmap's standing risks). Scope once decided: reservation windows on a dress/variant, interaction with item-based bookings (E3 #13's dress snapshot), and storefront presentation.

### Feature 29: Pre-scale gate: refund-API automation + k6 load pass + Redis caching (M)
The epic's ship gate for multi-tenant scale, three recorded debts from v1: **(a) refund-API automation** — invoke the refund call E4 #18 wrapped-but-never-invoked, replacing E4 #19's manual-console owner task; an automated money movement, so idempotent and audit-logged. **(b) k6 load pass** — deliberately cut from v1 (E4 #21), it gates multi-tenant onboarding. **(c) Redis slug/config caching** — the cache E1 #4 designed its middleware interface for, **including a bounded negative-result cache** per that feature's security review, so unknown-host floods can't hammer the DB. Gates #26's public launch.

---

## Risks

- **The dress "Reserved" semantics question (purchase/rental/made-to-order) is still open with the pilot** — recorded in the roadmap's standing risks. It blocks #28's spec, not the epic; resolve it during E4/pilot operation so #28 doesn't stall the epic tail.
- **Self-serve signup converts tenant creation from an audited operator action into a public endpoint** — slug squatting, junk tenants, and provisioning abuse become real. Mitigation is structural: #26 ships behind #29's gate, and its spec owns rate limiting + abuse controls explicitly.
- **The client bell has no realtime substrate until E6** (Pusher foundation is E6 #2). Poll-based in E5 is the assumption; if polling proves unacceptable at spec time, the alternatives are pulling E6 #2 forward or shipping the bell without live push — decide at #24's spec, don't let it inflate this epic.
- **Waitlist × deposit interplay is #23's hardest problem**: an offer claimed on a deposit-on type must not hold the slot forever (unpaid claim) nor lose it unfairly (paid-but-slow webhook). Same race-test discipline as E4 #19.
- **Refund automation moves money without a human in the loop** — wrong-amount or double-refund bugs are trust-destroying. Idempotency keys, amount assertions against the recorded payment, and audit-log entries are non-negotiable spec scope.

---

## Notes

- Specs are written when the phase starts, feature by feature — E4's recorded precedent. This file is the container, not the spec.
- The old roadmap bundle "#4 self-serve signup + web platform console + gateway-connect onboarding" was split (decision 2026-07-29) into #25 (operator-facing console) and #26 (owner-facing signup + gateway onboarding) — two audiences, two features.
- Downstream dependents: E6 #5's staff bell mirrors #24's client bell; E9's multi-fitting scheduling links into #24's dashboard + `.ics`.
- The waitlist race-safe design (sequential offers, expiry cascade, atomic conditional-update claim, partial unique index) is already recorded in `architecture.md` — #22/#23 specs start from it, not from scratch.
