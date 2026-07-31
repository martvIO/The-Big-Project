# Floor-management program — adversarial roadmap review, 2026-07-31

Produced by a 36-agent verification pass over commit `e67e787` (the queue re-order).
**30 findings raised, 0 survived** an independent skeptic pass. Verdict: safe to build as committed.

This file exists because the surviving value was not in the findings — it was in the
per-feature notes below. **Each feature's spec-writer must read its own section before
writing the spec.** These are things the queue note does not say and a spec author would
otherwise have to rediscover. LOOP-STATE remains the source of truth for scope; this is
supplementary detail, not a competing ruling.

## 3. FIX AT SPEC TIME

### F34 — shift-board-checkin (in flight)
- The spec's own §"Not built here" says F35/F37/F44 inherit *"D4's six mechanisms as a documented pattern and one interval constant — nothing executable"*. The floor block reassigns that inheritance to F57/F37/F41/F59. Keep the loop inside `BoardSection.tsx`; **do not pre-extract `usePoll`** — F57's queue entry claims the extraction and pre-empting it makes F57 unreviewable.
- SC 2.2.2 pause/idle (D14) is the one thing axe cannot see and the one thing the self-approved design gate no longer has a human checking. The named vitest assertions in the spec's test list are now the *sole* coverage of a legal requirement. Do not let them get cut as "redundant with the axe row".

### F57 — floor-staff-roles
- Widening `0011_staff_roles.py`'s `CHECK (role IN ('owner','shift_manager'))` needs DROP + ADD, and `Backend/tests/test_migrations.py::test_adding_the_role_check_validates_existing_rows` is the existing shape to copy for the widened set.
- `StaffRole` lives in `Backend/app/models/constants.py` and is consumed by `require_role` at 8+ call sites (`auth/staff_router.py:63`, `booking/owner_router.py:82`, `catalog/router.py:35`, `payments/router.py:30`). Widening the enum silently widens nothing — the route walker default-denies. Spell out, route by route, that the three new roles get **only** `GET /manage/floor` and their own break toggle, and add a walker assertion that pins it.
- `Frontend/apps/manage/src/App.tsx:17` — `SectionKey` is a local type, and NAV is a role-filtered readonly array since F52. The role filter is where a new role either appears or doesn't; that's a test, not an eyeball.
- Break toggle authorisation has two axes (owner/shift_manager on anyone, staffer on herself). The "on herself" branch is the one that leaks if the handler trusts a body-supplied `staff_user_id`.

### F36 — fitting-rooms
- The note does **not** demand RLS isolation probes; F41's does. `Backend/tests/` has six `test_*_isolation.py` suites and every tenant table in this repo has one. Add the probe requirement explicitly — three new tenant tables (`fitting_rooms`, `fitting_room_assignments`, dress bindings) ship in this PR.
- The `(tenant_id, staff_user_id) WHERE released_at IS NULL AND deleted_at IS NULL` index means a worker already holding a room gets an `IntegrityError` on her next claim. That must surface as a legible 409 ("she's still with a client") and not a bare 500 — `main.py` has no error registry, so an unmapped typed error *is* a 500 (F34 spec:252 makes this point).

### F33 — qr-walkin-queue (sharpest item in the block)
- **The `customers` invariant collides with the no-OTP ruling.** `Backend/app/models/customer.py:10-13` states customers are created *"ONLY after OTP verification proved possession of that number — an unverified phone would strand a paying customer behind an SMS link that can never arrive."* E6 explicitly excludes OTP from check-in, and the roadmap has F33 adding `customers.marketing_opt_in_at` and promoting opt-in tickets into `customers`. Decide it explicitly: either the opt-in flag lives on `queue_tickets` and no `customers` row is minted from unverified input, or the invariant is deliberately relaxed and that docstring is rewritten with the reason. Do not let it get quietly violated.
- **`CustomersRepository.upsert` cannot be reused as-is.** Its docstring (`Backend/app/db/repositories/customers.py:79-82`) says it is *"Safe to call without its own lock because every caller already holds the per-tenant advisory lock for the slot claim"*. Check-in has no slot claim and no advisory lock. Two simultaneous scans of the same phone race straight onto the partial unique index.
- **The three-field form drops pre-decided #26's marketing checkbox.** The note lists `(name, phone, bride/evening)` and separately adds `marketing_opt_in_at`. Ship the checkbox (default OFF, unbundled) or the column is dead on arrival and #26 is silently cancelled.
- **`called_at` must be in the public position payload from day one.** F33 (#4) freezes the customer-facing contract; F58 (#5) is what stamps `called_at`. If the payload only carries position/ahead-count/status, F58 has to amend a *public* contract to make "you're being called" reach the customer's own phone. Emit the flag now, always-false until F58.
- Rate limiters: two fresh `FixedWindowRateLimiter` instances wired in `Backend/app/main.py` alongside the existing eight. One budget = one instance — reusing `storefront_rate_limiter` or the OTP pair gives a busy bride morning a shared ceiling.
- `Backend/app/notifications/router.py` (`@router.post("/otp/send")`, `/otp/verify`) is the shipped precedent for a public mutating sibling on the `/storefront` prefix. Copy it rather than inventing; `test_storefront_api.py`'s cross-router shadowing guard covers the whole prefix and will catch a collision.
- QR generation is still undecided (e6 flagged it: no dep exists in the workspace). Pick one — small dep, inline generator, or operator-supplied image — in the spec. The route works from a typed URL regardless, so this must not become a blocker.
- Retention: auto-delete stays F20's job, and **F20 is parked**. Say plainly that F33 builds no retention job and that queue tickets accumulate until F20 lands.

### F58 — floor-dispatch
- **Take-next's room selection is unspecified and is the race the note doesn't cover.** The ticket claim is airtight (`SKIP LOCKED`), but "pick a free room" is a second selection: two managers pressing take-next at the same instant get two different customers and can still target the same free room, whereupon F36's index rolls the whole transaction back — the ticket returns to `waiting` (correct) but the manager sees a 409 while other rooms sat free. Spec the retry over the free-room set, or spec the explicit "no free room available" 409 and accept the spurious one.
- Who may dispatch? The note never says. Reception assigning a sales assistant to a room is plausible; a seamstress doing it is not. Name the roles.
- The `/manage/**` Playwright interception harness lands here. F34's spec:424 records why it doesn't exist (`vite preview` runs with no backend; the console's whole e2e surface is two login-screen tests at `e2e/a11y.spec.ts:10-13`). Budget it as real work, not a footnote.

### F59 — public-queue-board
- `deps: [F33]` is correct — `called_at` is F33's column, F58 only stamps it — but note it in the spec so nobody "fixes" the dep list.
- First names on a wall screen is the block's largest privacy delta and the one surface F20's eventual notice must cover. Record the hand-off the way F34's spec Risk 9 does.
- Its own SC 2.2.2 pause control needs a named frontend test; axe won't catch it, and unlike F34 there is no design gate behind it either.

### F37 — sos-paging
- **State the escalation's real bound.** Read-time predicate + 5s poll = a shift manager sees an unacked alert at 30–35s, not 30s. That's the right trade (the note argues it well against a 60s worker tick) but the spec should own the number rather than let a reviewer discover it.
- Delivery reaches a staffer only if she has a manage tab open and awake. #32 (in-app only) authorises that, but the brief said "the target's device" — write the narrowing down so it isn't rediscovered as a bug.
- The app-level ~2s tick while an alert is open runs for *every* signed-in staffer. Bound it: only the target and shift managers need the fast tick.
- Screen-reader announcement of an incoming alert is called a gate condition in the e7 Risks — that means a named test, same category as the pause control.
- RLS isolation probes for `sos_alerts` (not mentioned in the note).

### F41 — alteration-tickets
- The relabel is the trap: five nullable `TIMESTAMPTZ` columns whose *names* are now `intake_at`/`in_progress_at`/`qc_at`/`ready_at`/`delivered_at`, current state = latest stamped. No status enum, no event table. E9 had four states; QC is genuinely new.
- `due_date` replaces `wedding_date` everywhere including any E9 text that still says otherwise.
- Dress snapshot follows 0008's snapshot discipline; effort comes from Q13's five preset bands with the mapping in tenant settings, not hardcoded.

### F42 — seamstress-capacity
- Load = `SUM(effort_minutes)` over undelivered tickets. With the timestamp mechanism, "undelivered" is `delivered_at IS NULL` — a where-clause, not a status compare.
- Design gate is self-approved, so the a11y clause is the only guard left: the overload bar carries text, never colour alone, and the grid is keyboard-navigable.
- Overload flags, never blocks (#40). Sorting by remaining capacity is a hint.

### F60 — guide-walkthrough
- Export `SectionKey` from `App.tsx` (it's currently local) or the step map has nothing to key on.
- No tour library, no new dep — the note is right. Focus trap + Esc + restoring focus on close is the whole job, and it's the same class of bug F56 just shipped a fix for.
- Genuinely droppable. The note already says so; hold that line if the run runs long.

## 4. BRIEF GAPS

All nine brief items have an owning feature. The three narrowings below are deliberate and recorded — listed so nobody mistakes them for oversights:

- **Tri-lingual top bar** — deferred by explicit ruling (Hebrew only, no switcher; `ar` keys keep shipping untranslated per Q3).
- **SOS reaching "the target's device"** — narrowed to an open manage tab by #32. No push, no APNs/FCM, no SMS. A staffer with a locked phone is not paged.
- **Device-identity picker** — not ported, correctly: it existed only because the Firebase prototype had no auth.

The one genuine seam is **"being called" reaching the customer's own phone** — the brief pairs a per-entry *call* action with a *live position* view, but the call is stamped in F58 (#5) while the position payload is frozen in F33 (#4). Covered above under F33; it needs one field, not a feature.

Nothing else in the brief is unowned.

## 5. NOTHING-BURGERS

- Five poll loops end-state (board, floor, SOS, kanban, wall) — manage mounts one section at a time via `SectionKey`, so it's ~2 concurrent plus the app-level SOS. Fine.
- Seven migrations across ten PRs from HEAD 0013 — sequential loop, one at a time, no revision collision.
- F59's `deps: [F33]` omitting F58 — `called_at` is F33's column; the dep list is right.
- F32 "subsumed" while e6 still describes a versioned board-state substrate — F34's spec explicitly declines the version field and D13 declines the shared hook; both are argued, not forgotten.
- ROADMAP.md epic order now contradicts build order — the added banner says LOOP-STATE governs, and it does.
- F34's board polling `GET /manage/bookings?date=` while F57 adds a second 5s loop on the same screen — D13-sanctioned, two requests per 5s is not a load problem for one boutique.
- F19/F53 "cancelled" — they are not; file-order pick resumes them automatically, and the `current:` block says so twice.
- F53's blocker removal — the F21 *dep* still holds it, which is correct and is stated.