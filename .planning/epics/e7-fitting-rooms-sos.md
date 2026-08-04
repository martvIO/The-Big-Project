# Epic: E7 — Staff Coordination: Fitting Rooms & SOS

**Created**: 2026-07-30
**Status**: planning — briefs only, no spec yet. **Blocked on E6**: F36 needs staff identities and roles (F31), the live-update substrate (F32) and the board shell plus dispatch record (F34); F37 additionally needs the staff bell (F35). **Ships before E8** — Interview Q12, see Why. Everything here is buildable against the fake SMS provider F11 already shipped, but see Risks: staff cannot actually *sign in* in production until the SMS sender ID is registered, and an SOS reaches nobody who is logged out.
**Owner**: team
**PRD**: §9 (fitting rooms, staff↔client assignment, SOS paging)

> **AMENDED 2026-07-31 — the floor-management program.** `LOOP-STATE.md`'s `rulings_2026_07_31` and its `queue:` notes GOVERN this file wherever the two disagree. Both features are pulled forward and **F37 is amended on three points**: a 30-second unacknowledged **auto-escalation to the shift manager is reinstated** (overriding pre-decided #29's "no escalation timer"); targeting is a **specific signed-in colleague or the shift-manager role**, not a role fanout (the two were incompatible — escalating to the shift manager means nothing if the first page already reached every shift manager); and delivery is a **full-screen in-app overlay on its own alerts poll**, so **F35's bell is dropped from F37's deps**. Escalation is *derived at read time*, not stamped by the worker. What survives from #29: first-accept-owns, and a page is never silently dropped. The prototype's device-identity picker is **not** ported — MODRYN has real sessions. F36 additionally gains a **second** partial unique index on `(tenant_id, staff_user_id)`, so one worker holds at most one room.

---

## Why

E6 turns the shop floor into a screen: who is on shift, who is waiting, who is dispatched to whom. E7 is the half of that floor where the money is actually made and where a staffer is most alone — a closed fitting room with a bride half-dressed in a ₪12,000 gown. Two things are missing there. First, **nobody knows which room is free**, so two staffers walk a client to the same curtain; occupancy is a concurrency problem wearing a furniture costume, and it is the one thing on this floor that a screen can settle absolutely. Second, **the staffer in that room cannot ask for help without leaving it** — she needs a seamstress with pins, or a second pair of hands on a corset back, and today she opens the curtain and shouts.

**E7 ships before E8 (Interview Q12).** E8's weekly scheduler is a chore-remover: E6 already gives the owner a manual way to mark who is on shift, so the roster's absence costs her a few clicks a week and nothing else. Nothing at all substitutes for a staffer in a fitting room being able to call for help — there is no manual workaround for that, only shouting. E7 is also two features against E8's three, and the on-shift source it reads is deliberately E6's manual marking so that F40's published roster later replaces the source without touching either feature here (pre-decided #33, #41). The owner keeps ticking "on shift" by hand until E8 lands.

The epic's technical centre is one index. Pre-decided #31 fixes fitting-room occupancy as **one active assignment per room, enforced by a partial unique index** — the same structural guarantee F13 gave the booking slot. That is treated here with the same seriousness: a concurrency test, not a hope.

---

## Success Criteria

- [ ] A staffer claims a fitting room for a client and binds the dresses that went in with her; **a second claim on an occupied room is structurally impossible** — partial unique index on the room where the assignment is active, proven by a concurrency test to the same standard as F13's double-book test — and the loser is told who currently holds the room
- [ ] The board shows every room's occupancy, the assigned staffer with her role, the client label and elapsed time, all inside one ~5-second refresh tick; **releasing a room frees it for the next claim in the same tick**, and handing the client to a colleague preserves the room and its dress bindings
- [ ] A staffer raises an SOS by **role** ("I need a seamstress") from her own phone; every on-shift staffer with that role sees it in her bell, **the first to accept owns it** (a second accept is rejected and shows who owns it), the raiser sees who is coming, and resolution clears the alert from the live board into history
- [ ] With **no on-shift staffer in the requested role**, the alert is still created, routed to the shift manager, and the raiser is told so on screen — a page is never silently dropped, and an unaccepted page stays visible rather than expiring
- [ ] Both surfaces are Hebrew-first RTL on the existing `packages/ui` tokens, ship untranslated `ar` resource keys (Interview Q3), and pass the axe gate — **and the live alert announces itself to a screen reader**, since IS 5568 / WCAG 2.0 AA is a legal requirement and this is an emergency control (pre-decided #38)

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 36 | Fitting-room registry + staff↔client↔room↔dress assignment | **done (PR #37)** | `.planning/specs/fitting-rooms.md` | `.planning/plans/fitting-rooms.md` | F8, F13, F31, F34, F57 |
| 37 | SOS: targeted page, full-screen alert, ack/resolve, **30s escalation** | **done (PR #41)** | `.planning/specs/sos-paging.md` | `.planning/plans/sos-paging.md` | F31, F36, F57 · *F35 dep dropped 2026-07-31* |

**Order is F36 → F37 and it is forced, not chosen** (pre-decided #37). F37 attaches the raiser's current room to the alert so the responder knows where to go — that field is F36's assignment row, and without it an SOS says "help" without saying "here". Neither feature's design comes to the user: Q2 named only the staff shift board (F34) and the seamstress capacity matrix (F42) as novel patterns, so E7's screens assemble from F34's board shell and self-approve at the design gate.

---

## Feature Briefs

### Feature 36: Fitting-room registry + staff↔client↔room↔dress assignment (M)

Two tenant-scoped tables plus a child table, owner CRUD, and a panel on F34's board. It reads as an L until you notice the registry CRUD is a name and a sort order, and the board shell already exists — what earns real work is the claim.

**In.** `fitting_rooms`: label, display order, active flag, standard `id/tenant_id/created_at/updated_at/deleted_at`, TEXT not VARCHAR, no FK constraints, `enable_tenant_rls()` like every tenant table, partial index for active rows. Owner manages the list in `apps/manage` — a boutique types in "חדר 1 / חדר 2 / הבמה" once and never again.

`fitting_room_assignments`: `fitting_room_id`, `staff_user_id`, a nullable link to F34's dispatch record and a nullable `booking_id` (a booked bride walks straight past the queue; a walk-in arrives through F33's ticket), `assigned_at`, and `released_at` — **the nullable release timestamp is the whole occupancy model**. Active means `released_at IS NULL AND deleted_at IS NULL`, and the guard is `CREATE UNIQUE INDEX … ON fitting_room_assignments (tenant_id, fitting_room_id) WHERE released_at IS NULL AND deleted_at IS NULL` (pre-decided #31).

**How this differs from F13, deliberately.** F13's claim in `Backend/app/booking/service.py` takes `pg_advisory_xact_lock(hashtext(:tenant_id))` *and* leans on `idx_bookings_slot_seat_unique`, because picking `seat_index` requires counting the seats already taken — a count is a read-then-write, and only a lock makes that atomic. A fitting room has no seat to number: the claim is a single INSERT that either violates the unique index or does not. **F36 therefore needs the index and not the lock**, and the spec must not cargo-cult the lock in "for symmetry" — an `IntegrityError` becomes a 409 that names the current occupant, which is more useful to the staffer than a serialized wait. Release is a conditional `UPDATE … SET released_at = now() WHERE released_at IS NULL`; rowcount 0 means someone already released it, which is not an error.

`fitting_assignment_dresses`: one row per dress in the room, carrying `dress_id` plus name/size snapshots the way `bookings` snapshots them (0008's reasoning applies unchanged — the owner may rename or archive a dress mid-fitting). A child table rather than a JSONB array on the assignment specifically because two staffers add and remove dresses concurrently, and an array would be a read-modify-write race for no gain.

**The card.** Per-room tiles and per-staffer cards on F34's board: room label, staffer name + role from F31, client label, minutes elapsed, the dresses in the room. Actions: claim, add/remove dress, hand over to another staffer, release. Live via F32's ~5-second refresh — versioned board state with full refetch on version gap, server is truth (pre-decided #23, #25). No new transport.

**Client PII is deliberately not copied onto the assignment.** The card resolves the client label from the live dispatch or booking row at read time; it snapshots no personal field of its own. That is what keeps pre-decided #26 honest — a walk-in ticket auto-deletes a few days after the visit, and a snapshot on the assignment would quietly resurrect the data minimisation deleted. After the ticket is gone the historical assignment renders as an anonymous visit, which is exactly the "operational history retained, de-identified" shape pre-decided #34 requires.

**Out.** Booking a room in advance (rooms are claimed live, never scheduled). Capacity per room — a space that genuinely holds two brides is **two rows in the registry**, not a capacity column; adding one would destroy the structural guarantee this feature exists to give. Auto-assignment or room optimisation — a human picks the room. Occupancy timers, SLA alerts or anything that fires on elapsed time (the number is displayed, nothing watches it). Per-dress verdicts, ratings, photos or fitting notes — E9 owns alteration intake. The walk-in queue and the dispatch action themselves (F33/F34). Wait-time or room-utilisation analytics: pre-decided #28 keeps reporting out of E6 because there is no data to stand on yet, and that holds here too.

### Feature 37: SOS paging — role-targeted page, live alert, resolution (M)

**In.** She picks a **role**, not a person — "I need a seamstress" — and it pages every on-shift staffer with that role; the first to accept owns it (pre-decided #29). Roles are the existing `staff_users.role` / `StaffRole` enum in `Backend/app/models/constants.py` that F31 finally populates past `owner` (pre-decided #24); on-shift comes from whatever F31 exposes as the current-shift read, so F40's published roster later swaps the source underneath without a change here. No name picker, and none is wanted: on a shop floor you need a skill, not a colleague.

`sos_alerts`: `raised_by`, `requested_role`, optional one-line note, a nullable `fitting_room_assignment_id` so the responder knows which curtain to walk to, and `status` in `open → accepted → resolved` plus `cancelled` (the raiser sorted it herself). Accept is an **atomic conditional update** — `SET status='accepted', accepted_by=…, accepted_at=… WHERE id=… AND status='open'`; rowcount 0 is a 409 whose payload names the owner, so the losing responder learns "Dana has it" instead of walking into a solved problem. One row, no counting: no advisory lock, same reasoning as F36.

`sos_alert_targets` snapshots the paged set at raise time — one row per targeted staffer. Deriving the audience at read time from (role, currently on-shift) would be one table fewer, and it is wrong: a staffer who goes off-shift mid-page would lose an alert she may already have accepted, and "nobody was on shift for this role" would leave no evidence. The snapshot also gives the pilot the only number that matters for pre-decided #29's escalation question — how often a page went unanswered.

**Resolution flow.** The acceptor or the raiser marks it resolved; the alert leaves the live board and stays in history. The raiser can cancel any time before acceptance. **When nobody accepts, nothing expires and nothing re-routes** — that is the accepted consequence of #29's "no escalation timer". The alert stays open, keeps appearing in every targeted bell and on the shift manager's board (so a dropped page is loudly visible rather than silently lost), and the shift manager can accept it herself regardless of her own role — she is the universal fallback, which is the "or the shift manager" half of the roadmap's scope seed. **When there is no on-shift staffer in the requested role at all**, the alert is still created, targeted at the shift manager, and the raiser is told so on screen; the raise never fails.

**Delivery is the bell and only the bell** (pre-decided #32): F35's staff bell gains an alert kind. Nothing is written to `message_log` and no SMS is sent, so `message_log`'s `kind` CHECK and `MessageKind` are untouched by this feature. It rides F32's ~5-second refresh (pre-decided #23) — see Risks, which is where that decision earns its scrutiny. The SOS control lives in each staffer's own signed-in app on her own phone (pre-decided #27), reachable from the fitting-room card she is standing in.

**Out.** Escalation timers, auto-reroute after N seconds, ring-all-then-widen (#29 — layered onto the same alert record later if the pilot ever drops a page). SMS, push, APNs/FCM or a phone call (#29, #32). Paging a specific named person. Severity or priority levels, per-role response SLAs, and response-time analytics. Cross-tenant or cross-branch paging. A chat thread on the alert — the responder is walking to the room, not typing.

---

## Risks

- **A ~5-second poll is carrying an emergency page, and that is the decision here most likely to be revisited.** Pre-decided #23 buys no realtime vendor: worst case a page waits a full tick before it lights up a colleague's phone and another tick before the raiser sees the accept, so "help is coming" can take ~10 seconds while a bride stands there pinned into a gown. Accepted for a pilot floor where a shout still travels further than 10 seconds — but two upgrade paths are pre-authorised and both are cheap. First, without any vendor: the SOS feed is one row, so it may poll faster than the board's 5 seconds (a ~2-second tick while an open alert exists costs nothing). Second, pre-decided #23's Pusher swap — F32's API shape is identical either way (versioned events + full refetch, #25), so F37 needs no change to benefit. Owner: team, decided on pilot evidence; do not pull Pusher forward speculatively.
- **Externally blocked for production usefulness: staff login needs the SMS sender ID.** Interview Q11 put staff on phone + SMS OTP, so a staffer cannot sign in on a real shop floor until sender ID `MODRYN` is registered (`external-applications.md` #4) — and an SOS is worthless to a colleague who is logged out. E7 is fully buildable and testable now against F11's fake provider; only the live floor waits. **Owner: the user** — this is one of the standing `user_actions` in `LOOP-STATE.md` and nobody else can clear it.
- **Session lifetime is an operational trap Q11 created.** Every staff login costs an SMS and a ~30-second round trip. If staff sessions expire mid-shift, they expire at the worst possible moment and each expiry bills a message. F31 or F37's spec must set a deliberately long staff session on a trusted device rather than inheriting the owner-console default. Owner: team, at spec time.
- **Legally sensitive: a bride's name and her gowns on a screen in a public-ish room.** Amendment 13's minimisation duty is why F36 snapshots no personal fields and resolves the client label at read time (see the brief); erasure and retention then ride F20's retention job and pre-decided #34/#35's de-identification of operational history. The exact retention numbers stay flagged for **the owner's lawyer** to confirm at the F21 audit — the platform only enforces the clock. Owner: user's counsel for the numbers, team to enforce them.
- **Accessibility on an emergency control is a legal requirement, and the axe gate does not fully cover it.** IS 5568 / WCAG 2.0 AA is binding (pre-decided #38), and axe will catch contrast and labels but not whether a status change that appears only visually is announced at all: the live alert needs a proper live region, and accepted/resolved must never be colour-only. Add an explicit manual screen-reader check to the design gate for F37 rather than trusting the mechanical pass. Owner: team.
- **Estimates of who is on shift are only as good as the manual marking.** Until F40, on-shift is a checkbox the owner remembers to tick. A stale checkbox means a page targeted at someone who went home — visible on the manager's board (nothing is lost), but slower. This is the cost Q12 explicitly accepted in exchange for shipping SOS first; it disappears with F40.

## Notes

- E9 depends on E7 (ROADMAP): the alterations workshop attaches to the staff↔client assignment record F36 creates, and F42's capacity matrix reuses the seamstress role F37 pages. Nothing in E9 is in scope here.
- The walk-in queue, the dispatch action and the staff bell are E6 (F33, F34, F35). E7 consumes all three and adds none of them — pre-decided #28 put the staff↔client assignment record at E6's done bar precisely so this epic starts from it.
- Hebrew and Arabic copy is not specified in this file. Arabic resource keys ship alongside Hebrew and untranslated per Interview Q3 (mechanics in pre-decided #47); Hebrew wording is settled in each feature's copy deck at its design gate.
