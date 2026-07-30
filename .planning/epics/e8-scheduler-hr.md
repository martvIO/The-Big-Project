# Epic: E8 — Workforce: Weekly Scheduler & HR Directory (full)

**Created**: 2026-07-30
**Status**: planning — roadmap only. **E8 runs after E7 by Interview Q12**: E6's F31 already gives the owner a manual way to mark who is on shift, so E8 removes a chore, where E7 removes a safety hole (nothing substitutes for a staffer in a fitting room being able to call for help). No E8 feature gets a spec until E7 has shipped. Every feature still goes through `/spartan:spec` → `/spartan:plan` → TDD → dual review → PR (pre-decided #49), and all three self-approve at Gate 1 — none of F38–F40 touches payments, refunds, privacy-law *text* or tenant billing, which is the Q1 exception list.

**Numbering**: this file promotes the roadmap's E8-local stub (#1–#3) to the **global feature scheme** used by e1–e5 — #1→**F38**, #2→**F39**, #3→**F40** — and orders them exactly as pre-decided #37 fixes it (`E8: F38 HR → F39 availability → F40 roster`). The order is forced by dependency, not preference: availability is submitted against staff records, and a roster is built out of submissions.
**Owner**: team
**PRD**: §10 (weekly scheduler), §11.3 (HR directory, offboarding + retention)

---

## Why

E6 gave the boutique staff identities and a live board; it did not give it a **week**. Today the owner decides who works when in her head or on paper, and tells the system after the fact by ticking "on shift now" — a manual flag she has to remember to flip twice a day, per person, forever. That flag is also the input to two things that matter operationally: F34's board (who is here) and F37's SOS paging (who can answer "I need a seamstress"). A stale flag is a page that reaches nobody.

E8 closes that loop in three moves. **F38** finishes the staff record so a person is more than a login — a face on the board, an eligibility to run a shift, and a lawful end to the employment relationship that keeps the operational history while erasing the person. **F39** asks staff for next week instead of guessing it, on the phone they already sign in with. **F40** turns submissions into a published roster and then, the part that earns the epic, makes that roster the **single source of "who is on shift right now"** — retiring F31's manual marking as the primary answer without breaking the boutique that never publishes a roster at all.

The retention half is not decoration. Amendment 13 is in force, employee records are PII, and "keep everything forever, delete manually if asked" is the exact pattern regulators look for. Pre-decided #34/#35 settle the mechanics: soft-delete, retain operational history, and let F20's retention job blank the person at the legal boundary.

---

## Success Criteria

- [ ] A staff record carries a photo, a phone (her login identifier per Interview Q11), and a `shift_manager_eligible` flag distinct from her role; **offboarding soft-deletes her, revokes her sessions, retains every dispatch / room assignment / roster row she appears in, and registers her for a PII scrub 7 years after her last day** — the scrub blanks name, phone, email and deletes the photo object, and the operational rows survive de-identified
- [ ] Staff submit availability for **next week, Sunday-start**, against **owner-defined shift templates per weekday that were pre-filled from the boutique's existing opening hours** — not hardcoded tiers — from their phones after a phone + SMS OTP sign-in; the submission deadline is a tenant setting, and the owner can see who has not submitted
- [ ] The owner sets coverage targets per shift template per role, assigns staff against submissions with shortages **flagged but never blocking**, overrides an unavailable staffer with the override recorded, and publishes
- [ ] **The published roster is the answer to "is this person on shift now"** for F34's board, F37's SOS role-paging and F42's seamstress availability — with a same-day manual flag winning for that day only, and a week with **no published roster falling back to F31's manual marking unchanged**
- [ ] All three surfaces are Hebrew-first RTL on existing F9 tokens, carry untranslated `ar` resource keys, and pass the Playwright + axe gate (pre-decided #38 — IS 5568 / WCAG 2.0 AA is a legal requirement here as everywhere)

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 38 | HR directory full: photos, shift-manager eligibility, offboarding + retention scrub | todo | — | — | F31 · F8 · F20 · F9 |
| 39 | Staff availability submission (shift templates + weekly Sunday-start window) | todo | — | — | F38 · F31 · F11 · F12 · F7 · F9 |
| 40 | Roster builder + published roster as the current-shift source | todo | — | — | F39 · F38 · F34 · F37 · F9 |

**Sequencing is the pre-decided #37 chain and there is no parallelism worth taking.** F38 → F39 → F40 is a straight dependency line: F39's submission screen lists staff that F38 completed, and F40 assigns from submissions F39 collected. The only work that could start early is F39's `shift_templates` seeding (it reads F12's `availability_rules` and needs nothing from F38), and it is not worth splitting a feature for. **F40 is last and is the feature that changes shipped behaviour** — it rewires F34 and F37's read of "on shift" — so it should not be started while either is still settling.

---

## Feature Briefs

### Feature 38: HR directory full — photos, shift-manager eligibility, offboarding + retention scrub (M)

Completes the `staff_users` record F31 created. **No second identity table** — pre-decided #24 fixes the role set (`owner`, `shift_manager`, `reception`, `seamstress`, `sales`) on the existing `staff_users.role` column and `StaffRole` enum, and this feature adds columns to that row, nothing more.

**IN.** One staff photo per person, uploaded through **F8's existing presigned S3 pipeline** — tenant-prefixed key, `pending` → `ready` confirm that verifies magic bytes, exactly the `DressMediaStatus` two-phase pattern already shipped for dress media; no new storage path, no gallery, one photo. Purpose is identification on F34's board and F36's staff cards, and the spec states that purpose (see Risks). A `shift_manager_eligible` boolean **separate from `role`** — "may be assigned as the shift manager on a roster" is not the same claim as "her job is shift manager", and F40's role targets consume the eligibility, not the role. Profile completion: display name, **phone** (per Interview Q11 staff sign in by phone + SMS OTP, so the phone is the login identifier and must be present and unique per tenant), start date, nullable last day.

Offboarding per pre-decided #35: set `last_day`, soft-delete (`deleted_at`), revoke live sessions, and **retain every operational row** — F33 dispatches, F36 room assignments, F40 roster rows — joined by a `staff_user_id` that is never nulled. The FK-less, no-CASCADE schema makes retention the default and erasure the deliberate act, which is the right way round here.

Retention scrub per pre-decided #34: F38 registers a **staff data class in F20's retention job** and owns the scrub function — blank `display_name`, `phone`, `email`, delete the photo object from S3 — running **7 years after `last_day`**, with the 7 years a tenant setting rather than a constant so counsel's number is one row to change (pre-decided #10 lists the sibling periods). Operational history survives de-identified; that is the retention answer, not a gap.

**One code-level constraint to carry into the spec**: `Backend/app/models/staff_user.py` today declares `email` and `password_hash` as `nullable=False`, correct for v1's owner-only login. A phone-OTP staffer has neither. F31 is the feature that introduces phone login and should relax both columns; **if it did not, F38 carries that migration** — and the F38 code must not assume `email` is present on a non-owner row. The owner's email + password path continues to exist alongside OTP; Q11 accepted that cost explicitly.

**OUT.** Contracts and document storage, pay rates, hours worked, leave balances, performance records, org chart, any payroll export — this is a directory, not an HRIS. Also out: a re-hire flow (a returning staffer is a new row until the pilot asks for continuity), hard delete (soft-delete + scrub *is* the PPL erasure path per `architecture.md`), and any staff-facing edit of their own profile beyond the photo — the owner maintains the directory.

### Feature 39: Staff availability submission — shift templates + weekly Sunday-start window (M)

**IN.** `shift_templates`: owner-defined, per weekday, per **pre-decided #33 — shift tiers are templates, not three hardcoded bands.** On first open they are **seeded from the tenant's existing `availability_rules`** (`day_of_week` 0 = Sunday … 6 = Saturday, `open_time`/`close_time` — the Israeli week F12 already owns and F7 already lets the owner edit), so a boutique that entered its opening hours during setup gets a correct default week having been asked for nothing new. The owner may split, add, rename or remove templates per weekday. Saturday has no rules, so it has no templates and nothing to submit; a short Friday produces a short Friday template. Hardcoding tiers would bet that every boutique works the same week, and pre-decided #33 rejects that bet.

Submission is **weekly, Sunday-start** (pre-decided #36): a staffer sees next week's templates and marks each **available / unavailable / preferred** — three states, where "preferred" is advisory input to F40 and never a constraint. The **deadline is a tenant setting, not a hardcoded time** (pre-decided #36 — a hardcoded deadline becomes a support ticket per tenant), written through **F7's atomic single-statement settings merge** so a sibling key added by a later feature is never clobbered (the merge pre-decided #19 pins for F27 is the same one). After the deadline the week locks for staff; the owner can reopen it.

The flow is **phone-first because the identity is phone-first**: per Interview Q11 the staffer authenticates with phone + SMS OTP through **F11's existing primitive** — the same rate-limited, ≤5-minute, single-use send/verify customers use — and lands on a single-column, one-thumb list. Hebrew-first RTL on existing F9 tokens with the axe gate, `ar` keys added untranslated (pre-decided #38, Interview Q3). Plus one owner-side read: **who has not submitted for next week**, which is also the list F40 needs.

**OUT.** Standing/recurring availability ("never Mondays") — every week is submitted fresh in v1. Time-off and vacation requests with an approval workflow. Partial-shift availability (an hour inside a template). Shift swaps between staff. And **no automated deadline nudge**: the owner sees the not-submitted list and chases in person at pilot scale. If chasing turns out to be the chore, a nudge is a `scheduled_messages` row with a widened `kind` — F16's poller already does the hard part (the same widening pre-decided #16 authorises for waitlist offers) — and it costs an SMS per staffer per week, which is why it is not on by default.

### Feature 40: Roster builder + published roster as the current-shift source (L)

**IN.** The owner sets **coverage targets per (weekday shift template × role)** once; the builder shows target vs assigned per cell and **flags shortages without refusing to publish.** Advisory, matching pre-decided #40's posture in the workshop and for the same reason: the system has no view of who is sick, who owes a favour, or who covers two roles at once. Assignment reads F39's submissions — an unavailable staffer is assignable only through an **explicit manual override that records who overrode and when**, because a real Thursday needs cover regardless of what was submitted on Sunday. The shift-manager slot on each shift is fillable only from `shift_manager_eligible` staff (F38). Publish makes the week visible read-only to staff, immutable except by republish, and authoritative.

**The cutover — the actual risk in this feature, so it is spelled out rather than left to the spec.** One resolver, `is_on_shift(staff_user_id, at)`, becomes the single answer for every consumer: **F34**'s board, **F37**'s role-targeted SOS paging, and **F42**'s seamstress daily availability (pre-decided #41 already names the published roster as that source). Three rules, in order:

1. **A same-day manual flag set after the roster was published wins, for that day only.** Sick calls and unplanned cover happen after publish; without this rule an SOS page for "a seamstress" cannot reach the seamstress who actually walked in — precisely the failure F37 exists to prevent.
2. Otherwise, a **published roster row** for the week containing `at` is authoritative.
3. Otherwise — **no published roster for that week** — **F31's manual flag is authoritative, unchanged.** A boutique that never publishes keeps working exactly as it did in E6: the owner keeps ticking "on shift" by hand, which is the state Interview Q12 accepted while E8 waited.

So **F31's manual toggle is not deleted.** It is demoted from primary source to same-day exception channel, and it must be timestamped so rule 1 can tell "set today, after publish" from "left on since last month". The board labels which of the three rules produced the current answer, so a manager is never guessing why someone shows as off.

**OUT.** Pay, hours, overtime, and **any Hours of Work and Rest Law validation** (see Risks — this omission is deliberate and must stay visible). Auto-generated or optimised rosters — the owner assigns, the system counts. Multi-week publish. Copy-last-week (an obvious follow-up, deliberately not in the first cut). Staff-initiated swaps. Historical roster analytics — F42 computes its own metrics from timestamped job rows per pre-decided #41, and there is no reporting need here yet.

**Design gate.** Interview Q2 named **F34 and F42** as this program's genuinely novel interaction patterns needing a clickable prototype; the roster grid was **not** named, so it self-approves under Q2's familiar-screen rule (designer + `design-critic` must both accept). It is nonetheless the screen in this epic most likely to earn an escalation — if the critic rejects it twice, treat it as novel and bring the user a prototype rather than iterating a third time.

---

## Risks

- **The 7-year retention number is counsel's to confirm; the platform only enforces the clock.** Pre-decided #34 flags exactly this, and 7 years is the general Israeli practice for employment documents (10 for tax). It ships as a tenant setting, so a different number is one row. **Owner: the boutique owner's lawyer**, surfaced at F21's audit alongside F20's retention-period list (pre-decided #10).
- **Staff photos are employee PII under PPL Amendment 13.** Collection needs notice at the moment of capture and a stated purpose. F20 ships the platform-default Hebrew notice and Interview Q8 records that the default is **not lawyer-reviewed**; whether an employee photo needs separate written consent on top of the notice is a counsel question, and "identification on the in-store board" must not drift into monitoring. Platform mitigation shipped in F38: one purpose-limited photo, tenant-prefixed key, signed URL, deleted by the scrub. **Owner: the boutique owner's lawyer.**
- **Labour-law compliance is out of scope and must stay visibly out.** F40 validates coverage targets only — not daily hours, not the 36-hour weekly rest, not rest between shifts. A roster the builder lets you publish is not thereby a lawful roster, and no later feature may add a green checkmark that reads as legal clearance. **Owner: the boutique owner** (she is the employer; the platform is not an employment-law engine).
- **Production staff login is externally blocked; F39 is not.** Interview Q11 notes it directly: staff OTP rides the same F11 provider and the same Israeli SMS sender-ID registration that still gates production customer messaging (filed in E1 #2, still outstanding on the external-applications tracker). Build and test F39 against the fake provider exactly as F16 was built — that is Interview Q7's precedent — and let only real staff logins wait. **Owner: user** (the registration filing).
- **F38's scrub has no runner until F20 exists.** F20 is E4 and E8 follows E6/E7, so the ordering is safe — but F20 is one of the six features whose spec stops for the user (Interview Q1), so a slipped F20 leaves F38 shipping a registered staff data class and a scrub function that nothing calls. If that happens, park and record per pre-decided #2; do **not** stand up a second retention runner.
- **A published roster silently widens who gets paged.** After F40's cutover, F37's "page every on-shift seamstress" resolves against a roster a manager may have published a week ago. A stale roster pages people who are not in the building. Rule 1's same-day override is the mitigation; the honest residual risk is a manager who neither updates the roster nor flips the flag, and the pilot should be watched for it.

## Notes

- Interview Q12 is why this epic is third in the staff sequence rather than second: E6's F31 manual marking is a working, if tedious, substitute for a roster, and no equivalent substitute exists for a staffer in a fitting room needing help.
- Nothing here needs Pusher. Pre-decided #23 keeps the staff board on ~5-second refresh with no vendor, and a roster changes on human timescales; F40 publishes state, it does not stream it.
- `ar` resource keys are added alongside `he` in all three features, untranslated (Interview Q3) — the RTL layout Hebrew already pays for is the expensive half, so this is a translation job later rather than a retrofit.
- Hebrew copy is not decided in this file. Behaviour is specified here; strings are settled at each feature's design gate against the existing copy register (no exclamation marks — pre-decided #5).
