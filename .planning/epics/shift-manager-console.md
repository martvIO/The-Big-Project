# Epic: Shift Manager Console (SMC)

Feature interview 2026-07-30 (12 questions, user-answered) locked a shift-manager
persona for the manage console. Six features, six PRs off `main`, loop-compatible.
Full plan: authored in-session 2026-07-30; phases below.

## Overriding rulings (recorded so the loop reads rulings, not drift)

1. **Interview Q11 is overridden by user decision 2026-07-30**: staff sign in with
   **email + password** through the unchanged `/manage/auth/login` — no phone OTP,
   no SMS per login. F31 loses its sender-ID external blocker and its F11 dependency.
2. **E6's "gated on E4" program order is overridden** — this epic runs now.
   E6-proper (reception/seamstress/sales roles, QR queue, notification bell) stays queued.
3. Pre-decided #37's F31→F32→F33→F34 order is restructured: **F32 is subsumed into
   F34** as a client poll of the existing bookings API (no version field — computing
   it costs the same as answering in full); **F33 (QR queue tickets) is not built** —
   walk-ins become real bookings (F50's safe half).
4. F15 contingency exercised: SMC-1 started before F15's merge, gating the three
   shipped `/manage` routers. F15's `owner_router` adopts `require_role` on rebase
   (its D20 designed for exactly this swap); its `NotAuthorizedError` copy in
   `booking/owner.py` is dropped in favor of the one in `auth/dependencies.py`.

## Locked feature decisions

| Decision | Ruling |
|---|---|
| Persona | `shift_manager` — second `StaffRole`, near-owner permissions |
| Owner-only surfaces | staff management (whole router) + terms publishing (`POST /manage/terms`) |
| Staff login | email + password (Q11 override) |
| Staff management | full owner CRUD section |
| Dashboard | ops + customer KPIs; no revenue (payments unbuilt); forward-only utilization |
| Customers | CRM with notes + tags (`TEXT[]` on customers) |
| SMS log | read-only per customer/booking |
| Bookings section | F15's, untouched |
| Live board | full real-time (5s poll) + check-in (`checked_in_at` column, no new status) |
| Walk-ins | real bookings: `source='walk_in'`, no token, no SMS, NULL terms, checked-in at birth |
| Delivery | phased PRs, each through spec → (design gate where flagged) → build → review |

## Phases

| Phase | Queue id | Slug | Scope | Deps | Status |
|---|---|---|---|---|---|
| SMC-1 | F31 | staff-roles-gating | role enum + CHECK, `require_role`, default-deny gating on every `/manage` route, CI route-walker proof | — (F15 swap on rebase) | **done** (PR #22, hardening #23) |
| SMC-2 | F51 | staff-management | staff CRUD API + owner-only Staff section, role-filtered nav | F31 | **done** (PR #25) |
| SMC-3 | F52 | kpi-dashboard | `/manage/dashboard` aggregates + landing section | F31 | **done** (PR #28) |
| SMC-4 | F53 | customers-crm | search/detail/notes/tags + SMS log | F31 | queued — unblocked, but now **behind the floor program** in file order |
| SMC-5 | F34 | shift-board-checkin | `checked_in_at`, check-in/undo endpoints, 5s-poll board | F15, F31 | **done** (PR #32) |
| SMC-6 | F50 | walk-in-bookings | walk-in create from board (F50's safe half; remote owner-create stays open) | F34 | queued — blocked behind SMC-5 |

Three of six shipped. **Re-ordered 2026-07-31**: the user self-approved SMC-5's design gate, so the board is no longer parked — it is the **first pick of the floor-management program** (`LOOP-STATE.md` → `rulings_2026_07_31`) and the shell every floor panel attaches to (F57 staff cards, F36 rooms, F58 waitlist + dispatch, F37 SOS centre). SMC-6 (F50) unblocks the moment SMC-5 merges. SMC-4 is not cancelled — it simply sits below the floor block now, and the loop reaches it automatically once that block is exhausted.
