# Epic: E6 — In-Store Real-Time: HR Core, QR Queue & Shift Board

**Created**: 2026-07-30
**Status**: planning — roadmap + interview only. E6 is gated on E4 (ROADMAP program order); by the E4/E5 precedent no E6 feature gets a spec until v1 has shipped through F21's gate. **All five features self-approve at Gate 1** (Q1 names F17–F20, F29 and F48 as the only stops, and none of those is here) — with one trip-wire recorded under F33. **F34's design gate does NOT self-approve**: Q2 names the staff shift board as a genuinely novel pattern, so it comes to the user as a clickable prototype.
**Feature order is fixed** by pre-decided #37: F31 → F32 → F33 → F34 → F35.
**Owner**: team
**PRD**: §7 (walk-in queue), §8 (shift-manager live board), §11.3 core (staff records, roles, per-staff logins)

> **AMENDED 2026-07-31 — the floor-management program.** `LOOP-STATE.md`'s `rulings_2026_07_31` and its `queue:` notes GOVERN this file wherever the two disagree. Three features are added to E6 (**F57** floor roles + staff cards, **F58** waitlist + dispatch, **F59** public wall board) and two are re-scoped: **F33 is revived at full scope** — QR check-in *and* live position *and* the wall board — with its **F20 dependency dropped** (it adds the consent column itself, as the F33 trip-wire below already pre-authorised; only the collection-notice *wording* is parked as a user question), and **F34's design gate is self-approved**, so it no longer parks and is now the program's first pick. The forced order below (#37) is superseded by the floor block's order. Staff sign-in is **email + password**, not phone OTP — SMC ruling 1 settled that and F31 shipped it. Language scope for this program is **Hebrew only**; no switcher.

---

## Why

Everything shipped so far happens *before* the bride arrives. She browses, books, gets a text, walks in — and at that moment the software goes blank: it does not know who is working, who is free, who is standing at the counter, or who should take her. E6 is the first epic about the floor, and it exists to establish three things that E7, E8 and E9 all consume and none can be built without:

**Named staff who can sign in.** "Page a seamstress", "who is on shift", "assign this job to Noa" are all meaningless until a person is a row with a role and a session. Per Interview Q11 they sign in by **phone + SMS OTP**, reusing the F11 primitive customers already use — no work emails, no passwords, no reset helpdesk, and the OTP still resolves to a named `staff_users` row so per-person attribution survives for the Amendment 13 audit trail.

**The walk-in.** Today she is an entirely unrecorded, high-value lead standing in a doorway. Pre-decided #26 makes her a queue ticket by default — deleted a few days later — with one unbundled opt-in that promotes her to a real customer.

**A live surface that several phones agree on.** Pre-decided #23 buys **no realtime vendor**: ~5-second refresh polling, because `architecture.md` already mandates versioned events plus full-state refetch, so the API shape is identical either way and a 10-staff boutique needs under 20 connections. F32 is therefore a *live-update substrate*, not a websocket integration.

E6 stops at queue + dispatch (pre-decided #28): the manager assigns a named staffer and that staffer is notified. The dispatch record is precisely what E7's fitting rooms and E9's alterations hang off; wait-time reporting has no data to stand on yet and is not here.

---

## Success Criteria

- [ ] A named staffer with a **non-owner role** signs in on her own phone with phone + SMS OTP (Q11), receives a subdomain-scoped session that resolves to her `staff_users` row, and can reach only what her role permits — role cases added to the permanent CI cross-tenant isolation suite
- [ ] A walk-in scans the boutique's **one printed static QR** (pre-decided #30), submits her details, and appears in the day's queue with a **position computed on read**; a second scan from the same phone the same day updates her ticket instead of creating a second one
- [ ] The shift board, open on several staff phones at once (pre-decided #27 — a reception tablet is just one more signed-in device), shows on-shift staff with roles plus the live queue, and converges on server state within ~5s of any change, with a **full refetch on version gap or reconnect** (pre-decided #25)
- [ ] The manager **dispatches** a queue ticket to a named on-shift staffer; the assignment is recorded, appears on every board, and lands in that staffer's **in-app bell** — no browser push, no APNs/FCM (pre-decided #32)
- [ ] Every staff screen is Hebrew-first RTL on the existing `packages/ui` tokens, passes the blocking axe/Playwright a11y gate (IS 5568 / WCAG 2.0 AA, pre-decided #38), and ships `ar` resource keys untranslated (Q3)

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 31 | Staff records, roles & phone-OTP staff login | todo | — | — | F3, F5, F9, F11 |
| 32 | Live-update substrate (versioned board state + polling) | todo | — | — | F31 |
| 33 | QR self-check-in + queue tickets + live position | **done (PR #36)** | `.planning/specs/qr-walkin-queue.md` | `.planning/plans/qr-walkin-queue.md` | F5, F9, F10, F13 · *F20 dep dropped 2026-07-31* |
| 34 | Shift-manager live board + dispatch | **done (PR #32)** | `.planning/specs/shift-board-checkin.md` | `.planning/plans/shift-board-checkin.md` | F15, F31 · *design gate self-approved 2026-07-31* |
| 35 | Staff in-app notification bell | todo | — | — | F31, F34 |
| 57 | Floor roles (reception/sales_assistant/seamstress) + break status + staff cards | **done (PR #33)** | `.planning/specs/floor-staff-roles.md` | `.planning/plans/floor-staff-roles.md` | F51, F34 |
| 58 | Waitlist panel + dispatch (take-next, push-assign, finish, skip) | **done (PR #40)** | `.planning/specs/floor-dispatch.md` | `.planning/plans/floor-dispatch.md` | F33, F36, F57 |
| 59 | Public wall-screen queue board (`/queue`) | **done (PR #38)** | `.planning/specs/public-queue-board.md` | `.planning/plans/public-queue-board.md` | F33 |

**The order is forced, not preferred** (pre-decided #37). F31 is the identity layer everything else authorises against. F32 needs a signed-in staffer with a role before a board-state read can be authorised at all. F34 needs both plus something to show. F35's only producer in this epic is F34's dispatch, so a bell built first would have nothing to ring about. **F33 is the one that could float** — a public check-in form is technically independent of F31 and F32 — but its only consumer is F34's board, so building it third keeps it one poll away from being visible instead of dead data.

---

## Feature Briefs

### Feature 31: Staff records, roles & phone-OTP staff login (L)

**Pre-decided #24 verified against the code, and it is half-true.** `StaffRole` does exist in `Backend/app/models/constants.py` — but it declares **only `owner`**, with the comment "Owner-only in v1; the real role model gets its first consumer in E6". `staff_users.role` is `TEXT NOT NULL DEFAULT 'owner'` with **no CHECK constraint** (`migrations/versions/0003_auth.py`), unlike `message_log.kind` and `bookings.status`, which the DB pins. `sessions` do key on `staff_user_id`, as #24 claims. So the decision holds — reuse the column and the enum, no second identity table — but F31 must *extend* the enum to the five values (owner, shift_manager, reception, seamstress, sales) and add the CHECK the house pattern applies to every other bounded set.

**IN**: the enum + CHECK widening; a `phone` column with a partial unique index on `(tenant_id, phone) WHERE deleted_at IS NULL`; relaxing `email` and `password_hash` to nullable (a phone-only staffer has neither, and the existing partial unique index on `(tenant_id, email)` tolerates multiple NULLs in Postgres — the owner's email+password path is untouched); widening `StaffContext` (`email: str` is non-optional today) and `AuditAction`; **one new endpoint** exchanging an existing F11 verification token for a session cookie — the storefront `POST /storefront/otp/{send,verify}` pair is anonymous, tenant-from-Host and rate-limited already, so staff login adds a `/manage/auth` exchange and changes nothing inside `OtpService`; a **default-deny role gate** applied to the existing `/manage` routers; the manage HR screen (list / create / edit / soft-delete staff, set role); and **manual "on shift now" marking** — per Q12 the owner keeps ticking it by hand until F40's published roster replaces it, so this is an owner/shift-manager action, not staff self-check-in.

**OUT**: photos and shift-manager eligibility rules (F38); offboarding and the PII scrub (F38, running on F20's retention job); availability submission and roster building (F39, F40); staff self-service phone or role changes; any change to the owner's email+password login, which stays exactly as shipped; SSO of any kind.

### Feature 32: Live-update substrate — versioned board state + polling (S)

Pre-decided #23: **no vendor.** **IN**: one tenant-scoped, session-authorised board-state read that returns the whole board plus a monotonic `version`; one shared client hook that polls ~5s, pauses while the tab is hidden, refetches on focus, and on any version change **replaces state wholesale rather than merging** — pre-decided #25's "events are versioned hints, the server is truth" written as an API shape rather than a comment, so a later Pusher swap changes the transport only. Version derivation (greatest `updated_at` across the board's source rows vs. a per-tenant counter) is a spec-time call; the required property is that it is monotonic per tenant and moves whenever any input moves.

**OUT**: Pusher, websockets, SSE, any event bus or broker; client-side merging of partial events; channel naming and channel-auth layers (they arrive with the vendor, tenant-prefixed and server-authorised per pre-decided #25); optimistic local mutation — the board is a read surface, actions POST and let the next poll confirm. E9's workshop board assumes Pusher exists by then, which is the natural forcing point for that swap; it is a later feature's transport change, not a rewrite of this hook.

### Feature 33: QR walk-in check-in (M)

**IN**: a public `/checkin` route in `apps/storefront` (the hand-rolled router in `src/router.tsx` takes one `matchRoute` entry plus a doc-title key — no router dependency is added); the POST on a **mutating sibling router**, because `app/storefront/router.py` is contractually GET-only and `app/notifications/router.py` is the shipped precedent for exactly this; a tenant-scoped `queue_tickets` table whose **position is computed on read** from arrival order within the day and never stored (pre-decided #30 — stored positions must be renumbered on every insert, a race for no benefit); dedup by (tenant, phone, day) so a re-scan updates her ticket; **one unbundled marketing opt-in checkbox**, default OFF, that promotes the ticket into a `customers` row through F20's consent capture (pre-decided #26); F20's collection notice at the moment of collection; auto-delete a few days after the visit on F20's retention job (F20 already scopes "queue days" retention); and a printable static QR in the manage console pointing at `{slug}.modryn.co.il/checkin`.

**OUT**: OTP on check-in — she is standing at the counter, so possession proof buys nothing and would cost an SMS per walk-in; per-visit QR codes (they need a screen or printer at the door); stored queue positions; **bride-priority ordering** — FIFO by arrival until the pilot answers it, since it is an open product question in the roadmap's standing risks; wait-time estimates or analytics (pre-decided #28); check-in for customers who already hold a booking, which is a different path and not this one.

Two mechanics flagged for spec, neither able to block: no QR-generation dependency exists in the workspace (one small dep, an inline generator, or an operator-supplied image — the route works from a typed URL regardless), and `customers` today is only `(tenant_id, phone, name)` with no `marketing_opt_in_at`, so if F20 has not yet added the consent column, F33 does.

### Feature 34: Shift-manager live board + dispatch (L)

**Per Interview Q2 this is a NOVEL interaction pattern: it must come to the user as a clickable prototype at its design gate and does not self-approve** (designer + `design-critic` acceptance is not sufficient here, unlike every other screen in this epic).

**IN**: one board screen running on each staff member's own phone, signed in as herself (pre-decided #27); on-shift staff with role badges; the day's queue in arrival order; and the **dispatch action** — assign a ticket to a named on-shift staffer, writing the assignment record (ticket, `staff_user_id`, dispatched_by, dispatched_at) that pre-decided #28 identifies as the real output of this epic and that E7's fitting rooms and E9's alterations both build on. All data arrives through F32's poll; dispatch is role-gated to shift_manager and owner, everyone else reads.

**What "that staffer is notified" means before F35 exists**: the assignee is already looking at her own board, so she sees her assignment within one poll. F35 upgrades that from a glance to a persistent, unread-tracked bell — it does not create the notification obligation, it fulfils it durably.

**OUT**: wait-time analytics and any owner reporting (pre-decided #28); fitting-room occupancy (F36); SOS paging (F37); roster editing (F40); drag-to-reorder the queue; read-only display/kiosk mode (pre-decided #27 calls that a small follow-up if the pilot asks for it).

### Feature 35: Staff in-app notification bell (M)

**IN**: a tenant-scoped `staff_notifications` table (staff_user_id, kind, entity reference, `read_at`); unread count, list and mark-read; a bell in the console header — which needs a new slot on `ConsoleShell` in `packages/ui`, a gate-passed component, so the design gate is touched; and delivery **on F32's existing poll**, sharing its version so the bell never runs a second timer. F34's dispatch is its first and only producer in this epic; F37's SOS becomes the second.

**OUT**: browser push, APNs/FCM, service workers (pre-decided #32 — a push stack is E10-scale work and the bell's consumers are already looking at the app); SMS or email fan-out of in-app notifications; per-staffer notification preferences; grouping or digesting; the **customer** bell, which is F24 — a different app, a different substrate, and no dependency in either direction.

---

## Risks

- **Production staff login is externally blocked; the build is not.** Q11 puts staff on the customer OTP path, so a real staff login needs the Israeli SMS sender-ID registration — an unfinished `external-applications.md` item, **owner: the user**, and the same item gating F16. Build against the shipped fake sender plus dev code, exactly the play Q7 approved for payments; nothing in F31 waits on it.
- **Every staff login costs an SMS, every day, per staffer** — accepted in Q11. The OTP body (`קוד האימות שלך: …`) is one UCS-2 segment where Q4's reminder is three, so the unit cost is a fraction of the ~$0.77 the interview priced, but it recurs per login and lands in F48's metered-messaging line. **Owner: operator.** The lever is session lifetime, decided at F31's spec — not a second auth mechanism.
- **Staff logins share the customers' OTP send budget.** The per-tenant and per-phone budgets are single `FixedWindowRateLimiter` instances in `Backend/app/main.py`, and one instance is one ceiling per key: a bride-heavy morning that trips the tenant ceiling stops staff from signing in, and the per-phone path answers 204 without sending by design, so the failure is silent. F31's spec must give staff login its own limiter instance. **Owner: team.**
- **Roles turn every existing `/manage` endpoint into an authorisation question.** Today every staff row is `owner` and every manage route means "any valid session". The moment reception can sign in, catalog, hours, terms and settings are reachable by her unless F31 ships default-deny gating and extends the permanent isolation suite with role cases. This is the epic's most likely security defect. **Owner: team**, at F31's spec and its dual review.
- **Walk-in check-in collects PII from the public at the door — legally sensitive.** Amendment 13 requires notice at the moment of collection and Israel's Spam Law requires the marketing opt-in to be separate and unbundled (pre-decided #26). F33 uses F20's platform-default Hebrew notice, which per Q8 is **not lawyer-reviewed**; counsel sign-off is the same pending gate as the SMS bodies (Q5). **Owner: the boutique's counsel, via the operator.** Trip-wire on Q1: F33 self-approves at Gate 1 only because it *consumes* F20's privacy text — if its spec concludes it must author check-in-specific privacy-notice wording, that is privacy-law text and the spec stops for the user.
- **Staff phone numbers and dispatch history are employee PII.** Per-person attribution must survive for the Amendment 13 trail (Q11) while pre-decided #34 auto-erases personal fields 7 years after last day on F20's retention job — enforced in F38, not here. F31 must not shape the staff record so that scrub becomes impossible: personal fields have to be separable from operational history. The 7-year number is **the owner's lawyer's** to confirm; the platform only enforces the clock.
- **IS 5568 / WCAG 2.0 AA is a legal requirement, and the board is the hardest screen in the product.** A dense role/status matrix at 375px that mutates every five seconds: announcing a change without narrating the whole board on every tick is the specific unsolved problem, and Q2's prototype gate exists for it. The axe/Playwright job is blocking CI (pre-decided #38).
- **Polling's ceiling is measured at the pilot, not assumed now.** ~5s across ~10 devices is roughly two board-state reads per second per tenant against RLS-scoped queries; pre-decided #23 judged that fine at boutique scale and pinned the escape hatch — Pusher behind F32's unchanged API shape. **Owner: team**, at pilot review, with E9's workshop board as the natural forcing point.

## Notes

- Pre-decided #24's premise was checked and corrected in F31's brief rather than at spec time: the enum exists but holds one value, and the role column has no CHECK. The decision itself (reuse the column, no second identity table) stands.
- Downstream consumption, so later epics start from these and not from scratch: F36/F37 (E7) need F31's roles + on-shift status and F34's assignment record — pre-decided #29 routes SOS by role precisely because E6 already stores role and on-shift state. F40 (E8) **replaces** F31's manual on-shift marking as the "current shift" source (pre-decided #33). F41/F42 (E9) treat seamstresses as F31 staff rows with the seamstress role.
- Arabic per Q3 and pre-decided #47: both apps' i18next init currently registers `he` only (`src/i18n/index.ts` in each), so every feature here adds an `ar` bundle beside it, untranslated, and reuses the RTL layout wholesale — no direction-switching logic, no second stylesheet.
- This file is the container, not the spec. Specs are written feature by feature when the phase starts, per the E4/E5 precedent.
