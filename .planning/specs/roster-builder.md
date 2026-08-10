# Feature 40 — Roster builder + the published roster as the current-shift source

**Epic**: E8 · **Size**: L · **Deps**: F39 (PR #58, merging) · F38 (merged, PR #55) · ~~F34~~ · F57 · F37 · F9
**Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals (Q1).**

F40 self-approves. Q1's stop-list is *payments, refunds, privacy-law **text**, tenant billing*; F40 authors
none of it, stores no new personal data (D16), and adds no legal wording. Two things are worth naming
before the first decision, because both are load-bearing and both contradict the brief:

1. **There is no F31 on-shift toggle.** The epic's whole framing — "a manual flag she has to remember to
   flip twice a day, per person" — describes a mechanism that was never built. Nothing in the codebase
   stores, reads or writes "on shift". F40 therefore **introduces** the notion rather than superseding
   one, and the cutover is additive, not a swap (C1).
2. **This is still not an hours-worked record.** The epic's labour-law risk row binds harder here than it
   did on F39: a roster with times on it is one `SUM()` away from a timesheet. No screen in this feature
   totals an hour, and no column here may ever be read as attendance. That drift is review-blocking.

---

## Verified against the codebase (2026-08-10, `main` @ `d65344f`, plus `feature/availability-submission`)

| Claim | Reality |
|---|---|
| "On shift" today | **Does not exist.** `grep -rn "on_shift\|is_on_shift" Backend/app` returns nothing. `FloorService.read` calls `StaffUsersRepository.list_live` (`db/repositories/staff_users.py:37-45`) = `tenant_id = ? AND deleted_at IS NULL`, ordered `created_at`. Every live staffer is on the board, always |
| The staff board | **F57's `FloorPanel.tsx`, not F34's** — `GET /manage/floor` → `FloorResponse.staff[]`. F34's `BoardSection.tsx` polls `GET /manage/bookings?date=` and carries no staff row at all (C6) |
| Card status | `floor/service.py:136-150` `card_status(row, *, occupied)` → `StaffCardStatus` = `OCCUPIED > BREAK > AVAILABLE`, **derived on read, never stored**. `break_started_at` is the only per-person mutable state and it means *on break*, not *on shift* |
| `StaffCard` keys | **EIGHT**, pinned by `STAFF_CARD_KEYS` set-equality in `test_floor_api.py:80-89`. F38's comment: *"the set-equality assertion over it is what catches a seventh arriving unreviewed"* |
| FE status map | `FloorPanel.tsx:53-57` `STATUS_BADGE: Record<StaffCardStatus, …>` with **no fallback** — a fourth status is a compile error by design |
| F37 SOS targeting | `sos_alerts.target_staff_user_id` is a **named staffer or NULL**; NULL = the audience `{owner, shift_manager}` (`models/sos_alert.py:45-50`). Reachability for a named target is `SessionsRepository.has_live_session` — a **session**, not a roster. **The role route gets no probe at all** and its audience can be empty; `floor/service.py:1597-1622` records that as Risk 3(a), a known ceiling. There is no "page every on-shift seamstress" anywhere (C2) |
| F42 seamstress availability | `atelier/schemas.py:212` `assignable = row.deleted_at is None and row.role == StaffRole.SEAMSTRESS.value`. LOOP-STATE:1260 — *"the F40 dep is DROPPED for this run … the F40 published-roster projection … is the recorded upgrade path, NOT this build"* (C3) |
| `shift_manager_eligible` | `models/staff_user.py:56-62`, `BOOLEAN NOT NULL DEFAULT false`, F38's 0032. Its own comment: *"'may be assigned as shift manager' is not 'her job is shift manager'. F38 stores it and enforces nothing; **F40 is its only consumer**"* |
| F39 tables | `shift_templates` (day_of_week, label, starts_at_time, ends_at_time, sort_order) · `staff_availability` (staff_user_id, shift_template_id, week_start DATE, state, recorded_by), both `SoftDelete`+RLS, migration `0035_shift_availability.py` |
| F39 pure rules | `app/shifts/validation.py` — `current_week_start`, `week_end` (**inclusive Saturday**), `default_week_start` (**next** week), `validate_week_start` (Jerusalem Sunday), `assert_readable_week` (±4), `assert_writable_week` (forward-only), `deadline_at` (DST-safe), `scheduling_pair`, `MAX_TEMPLATES_PER_DAY=6`, `MAX_TEMPLATES=42` |
| F39 states | `AvailabilityState` = `available \| unavailable \| preferred`, DB-pinned. **No `pending`** — absence of a row is "not answered" (D8). `preferred` is *advisory input to F40 and never a constraint* (F39 O2) |
| F39 invalidation | `StaffAvailabilityRepository.soft_delete_future_by_template` — a material template edit kills future answers **in weeks `> current_week_start`**; past and current are untouched *"and F40 may already have published off them"* (F39 D4) |
| Shifts router | `app/shifts/router.py` — `prefix="/manage"`, `dependencies=[_no_store, require_role(*StaffRole)]`, per-route `ELEVATED = require_role(OWNER, SHIFT_MANAGER)`. Eight routes. `vite.config.ts` alternation already carries `shifts` |
| Elevated predicate | `floor/service.py:101` and `shifts/service.py:77` each spell `ELEVATED_ROLES = frozenset({OWNER, SHIFT_MANAGER})` **locally**; `floor/service.py:1924` is the shipped self-or-elevated guard raising `NotAuthorizedError` (403) |
| Boutique clock | `storefront/validation.py:40,86` — `BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")`, `today_jerusalem()`. Week index `booking/validation.py::jerusalem_day_index` = `(date.weekday()+1) % 7`, FE twin pinned by `test_frontend_constant_parity.py` |
| Retention registry | `app/privacy/retention.py:486-503` `POLICIES` — **EIGHT**, counted from source: `otp_codes, sessions, queue_tickets, waitlist_entries, message_log, bookings, customers, staff_users`. The coverage test is a **set equality** |
| Audit action column | `audit_log.action` is plain TEXT with **no CHECK** (`0003_auth.py:71-79`). Twelfth feature block to rely on it; no migration |
| Migration head | **`0034_platform_invites.py` on `main`** (F26 merged); F39 holds `0035_shift_availability.py` on its branch. Build at head+1 **at build time**, renumber at rebase (`.memory/parallel-alembic-numbering`) |
| Walkers | `test_cross_tenant_walker.py` (pinned pair — `(67, 65)` on `main`, **`(70, 68)` once #58 merges**; `_MODULE_BY_PREFIX`, `MODULE_WALK_FLOOR`), `test_audit_coverage.py` (`UNAUDITED_BY_DECISION`), `test_staff_role_gating.py` (`OWNER_ONLY`, `NON_ELEVATED_REACH`, `FLOOR_OPEN`, `ATELIER_OPEN`, F39's `SHIFTS_OPEN`/`SHIFTS_ELEVATED`), `test_spa_serving.py`, `test_frontend_constant_parity.py` |
| Model parity | `test_boutique_models.py:110` (`staff_users` ↔ 0032) and F39's `:160` (`shift_*` ↔ 0035). The **only** model↔migration parity mechanism in `Backend/tests` — F40 ships its twin |
| Nav | After F39: owner **16** rows, shift manager `.slice(0, 13)`, `shifts` row carries `EVERY_ROLE` and sits immediately after `atelier`. `Nav.test.tsx`: *"a nav row is five coordinated edits, not one"* |
| Touch floor | `packages/ui/src/components/Button.tsx` — `sm: min-h-9` (36 px) **fails** the 44 px floor. `md` only |

---

## Conflicts recorded (the brief predates shipped reality)

**C1 — F31's manual on-shift flag does not exist, so there is nothing to demote.** The epic states it four
times ("E6's F31 already gives the owner a manual way to mark who is on shift"; "a manual flag she has to
remember to flip twice a day, per person, forever"; "F31's manual flag is authoritative, unchanged";
"F31's manual toggle is not deleted, it is demoted"), and LOOP-STATE's own F40 note repeats it. **None of
it is true against the code.** F31 shipped the `shift_manager` role member and default-deny `/manage`
gating and nothing else (LOOP-STATE:2576-2601 — its scope line is explicit). The only per-person mutable
state on `staff_users` is F57's `break_started_at`, and F57's own comment calls a lingering break *"a
stale toggle nobody cleared"* — it is the opposite of an on-shift flag.

What is actually shipped is **liveness as an implicit on-shift claim**: `list_live` returns every
non-deleted staffer and the board renders all of them. **That** is what F40 demotes. After this feature,
`deleted_at IS NULL` means *on the payroll*, and a separate, labelled resolver answers *on shift*.
Rule 3 ("no published roster ⇒ F31's manual marking, unchanged") therefore resolves to **"every live
staffer counts as on shift"** — which is precisely today's behaviour, so a boutique that never publishes
sees **no change at all**. That is the correct discharge of the epic's promise, and it is cheaper and
safer than the swap the brief describes.

**C2 — F37 does not page "every on-shift seamstress", and F40 must not make it.** The brief's cutover
names F37's *"role-targeted SOS paging"* as a consumer and the Risks section warns that *"a published
roster silently widens who gets paged."* Verified: `sos_alerts` has **no role column**. A page is either
at one named staffer or at NULL, and NULL means the two-member elevated audience — a pure `actor.role`
test computed at read time in `_for_me`, with no query. The one reachability probe that exists reads
`sessions.has_live_session`, i.e. **is she signed in right now**, which is a strictly better proxy for
"is she in the building" than a roster published a week ago. **Resolved: F37 is not rewired** (D15).
Wiring the roster in would page people who are rostered but logged out and un-page people who walked in
and signed in — it would *create* the epic's own stated risk rather than mitigate it.

**C3 — F42's dependency on F40 was already dropped, in writing.** The epic's success criterion names
*"F42's seamstress daily availability"* as a consumer and cites pre-decided #41. F42 shipped without it
(LOOP-STATE:1260-1265): capacity is `staff_users.weekly_capacity_hours` against a tenant default, and
`assignable` is `deleted_at IS NULL AND role = 'seamstress'`. The published-roster projection is named
there as *"the recorded upgrade path, NOT this build"*. **Resolved: F42 is not rewired** (D15). F40 ships
the seam; adoption is a later, separately-reviewable edit to one derived boolean.

**C4 — "the owner … publishes" narrows a predicate the codebase already spells wider.** The brief's IN
paragraph puts every builder verb on the owner. `ELEVATED_ROLES` — `{owner, shift_manager}` — is the
shipped predicate for *"may act on anyone"* across breaks, room claims, handover, dispatch, queue skip
and F39's on-behalf availability write. `OWNER_ONLY` in the role-gating walker holds staff CRUD, the
payment gateway and privacy — capabilities about *the business*, not *the floor*. A roster is a floor
artefact. **Resolved: build, publish and the same-day override are all `ELEVATED`** (D13). A shift manager
who may assign but not publish has built a roster nobody can see, and this console has no
submit-for-approval concept to give her.

**C5 — "immutable except by republish" describes a state machine worth not building.** Taken literally it
needs a published week to refuse edits until an explicit unpublish, which invents a third state (published
→ unpublished → republished) in which a week that *was* authoritative silently is not. **Resolved (D7):
publishing is idempotent, a published roster stays editable, every edit takes effect on the next read, and
there is no unpublish.** The honesty the brief was buying comes from `published_at` being visible on the
pane and from the board's rule label, not from a lock.

**C6 — `deps: [F34]` names the wrong board.** F34 is `BoardSection.tsx` polling `GET /manage/bookings?date=`
— the day's bookings, no staff row anywhere. The screen that must carry the rule label is **F57's
`FloorPanel.tsx`** reading `GET /manage/floor`. The dep list is corrected in this header. This is the
same class of error LOOP-STATE:1289 already caught once on F60 (*"`deps: [F34]` is WRONG in the way that
matters"*), and it matters here for the same reason: it points the build at a file it must not touch.

---

## IN

1. **`rosters`** — one per (tenant, week), draft until published. `published_at` / `published_by` are the
   whole of its state; a draft is never authoritative (D6).
2. **`roster_assignments`** — (roster × shift template × staffer), with `is_shift_manager` and the
   recorded override of an `unavailable` submission.
3. **Coverage targets** per (shift template × role), as a JSONB column on F39's `shift_templates` (D10).
   Target vs assigned is **displayed and flagged, never enforced** (pre-decided #40).
4. **The resolver** — `on_shift_at(...)`, three ordered rules, returning both the answer **and which rule
   produced it** (D2, D8).
5. **The same-day manual override** — two columns on `staff_users`, two-valued, expiring at Jerusalem
   midnight with no sweep (D3, D4).
6. **The floor board's cutover** — `StaffCard` gains `on_shift` and `on_shift_source`; the board **labels
   and never filters** (D1, D9); an elevated actor gets the override control beside the break toggle.
7. **The roster pane** in F39's existing `shifts` section, plus her own published shifts on `MyWeekPanel`.

## OUT

Pay, hours, overtime, **any Hours of Work and Rest Law validation** (epic risk: *must stay visibly out*) ·
auto-generated or optimised rosters · multi-week publish · copy-last-week · staff-initiated swaps ·
historical roster analytics · rewiring F37's SOS (C2/D15) · rewiring F42's `assignable` (C3/D15) ·
filtering anyone off the floor board (D1) · a per-week coverage target (targets are per template, D10) ·
notifying staff that a roster published (an SMS per staffer per week, F39's OUT for the same reason) ·
polling on any surface this feature adds · overnight shifts (F39's DB CHECK bars them) · a new nav row (D14).

---

## Decisions

### D1 — The board LABELS; it never filters

`FloorService.read` keeps calling `list_live` and keeps returning **every live staffer**. `StaffCard` gains
two keys; no row is removed and no row is reordered.

**Rejected — filtering the board to on-shift staff.** It is the obvious reading of "the published roster is
the answer to who is on shift", and it breaks the screen. `GET /manage/floor` is what a seamstress opens to
find out who else is in the building; the moment a roster is published, a colleague who walked in anyway —
covering a sick call, collecting something, working a day nobody rostered — vanishes from it. She is
standing in room 2 with a bride, and `card_status` would still say `occupied` about a card nobody can see.
Worse, the failure is silent and looks like an empty boutique. F57's own comment on `card_status` settles
the principle: *"telling a shift manager looking for help that the person she can see in room 2 is «בהפסקה»
is the screen lying about something visible."* A hidden card is the same lie with the evidence removed.

**Rejected — a separate "who is on shift" screen.** A second list of the same people, differing only in a
predicate, is where the two lists disagree.

The demotion C1 describes happens here and only here: `deleted_at IS NULL` stops answering "on shift" and
goes back to answering "employed". The answer now comes with its provenance attached.

### D2 — The resolver is a pure function of three inputs, in `shifts/validation.py`

```python
def on_shift_at(
    *,
    override_on: datetime.date | None,      # staff_users.on_shift_on
    override_value: bool | None,            # staff_users.on_shift_override
    roster_published: bool,                 # a live rosters row for `at`'s week with published_at NOT NULL
    rostered_now: bool,                     # she has an assignment whose template covers `at`
    local_date: datetime.date,              # `at` in Asia/Jerusalem
) -> tuple[bool, OnShiftSource]:
```

Three ordered rules, and the tuple is the point — **the answer and the rule are computed together, so they
cannot disagree.** `OnShiftSource(StrEnum)` = `MANUAL_TODAY | ROSTER | FALLBACK`, **derived and never
stored**, so it gets no DB CHECK (`StaffCardStatus`' rule, not `AvailabilityState`'s).

```
1. override_on == local_date          -> (override_value, MANUAL_TODAY)
2. roster_published                   -> (rostered_now,   ROSTER)
3. otherwise                          -> (True,           FALLBACK)
```

It lives in `app/shifts/validation.py` beside `deadline_at` because that module is already the home for
this feature's pure rules and does no I/O — which is what lets the whole three-rule matrix be a **fast-lane**
test with no Postgres and no fakes. `FloorService` gathers the four inputs and calls it; nothing else
computes an on-shift answer anywhere.

**Rejected — a `FloorService` method.** The one caller today is the floor read, but D15 records F37 and F42
as future adopters and a rule they have to reach through a service they do not depend on is a rule that
gets re-implemented.

### D3 — Rule 1 is a same-day, two-valued override, and there is NO comparison against `published_at`

The epic phrases rule 1 as *"a same-day manual flag **set after the roster was published** wins."* The
publish comparison is **rejected**, and the reason is a concrete failure it causes: the owner marks Dana off
for Sunday at 08:00 (sick call); at 15:00 she edits **Thursday's** shift and republishes; `published_at`
moves past Dana's flag; Dana silently reappears as on-shift on the board for the rest of Sunday. An edit to
one day must not revoke an override on another.

What the comparison was reaching for — *"tell 'set today' from 'left on since last month'"* — is delivered
completely by **scoping the override to a Jerusalem calendar DATE**. An override for a day that is not today
is not consulted, so it cannot be stale by construction. No clock comparison exists to get wrong.

**The override is two-valued** (`true` = on shift, `false` = off shift), not a one-way "mark her on".
Rejected — a one-way flag: the commonest same-day event in a boutique is somebody **not** coming in, and a
flag that can only add people cannot express it. That is also the rule that makes rule 1 useful in a
boutique with no roster at all (rule 3 says everyone is on; `false` is the only way to say otherwise).

### D4 — The override is two columns on `staff_users`, and it expires with no sweep

```
on_shift_on       DATE      NULL   -- the Jerusalem day this override speaks for
on_shift_override BOOLEAN   NULL   -- true = on shift, false = off shift
CONSTRAINT staff_users_on_shift_pair_check CHECK ((on_shift_on IS NULL) = (on_shift_override IS NULL))
```

**No table**, F38's six-photo-columns argument applied unchanged: one override per person per day, only
today's is ever read, so there is no sort order, no per-parent cap, no count, no sweep loop and no list. A
table would buy a repository and an RLS policy to express "at most one".

**No `set_at`, no `set_by`.** `on_shift_on` already carries everything rule 1 needs, and the durable record
of *who* flipped it and *when* is the `ON_SHIFT_OVERRIDE_SET` audit row — F38's precedent verbatim (*"that
row is the **only** durable record"*). Two columns that are read are better than four of which two are not.

**This is the answer to "what stops it becoming a permanent override nobody notices."** It cannot. At
Jerusalem midnight the date stops matching and rule 2 or 3 answers again, with **no worker, no scheduled
job and no writer** — the same compute-on-read discipline `card_status`, F37's escalation and F36's
occupancy already use, and for F37's stated reason: a worker-stamped expiry would arrive up to a
`worker_poll_interval_seconds` late and would race a concurrent write. The stale row stays on the table and
is simply never consulted; the next override overwrites it.

### D5 — Rule 2 keys on the EXISTENCE of a published `rosters` row, never on assignments

"Published with nobody on this shift" and "no roster published" are **different answers** and the code must
be able to tell them apart:

- published + no assignment covering `at` ⇒ `(False, ROSTER)` — she is genuinely not on shift, the owner
  said so by publishing a week that does not include her.
- no published roster ⇒ `(True, FALLBACK)` — the boutique has not told the system anything, so the system
  does not pretend to know.

Deriving "published" from `EXISTS(assignments)` collapses the two, and it collapses them in the dangerous
direction: an owner who publishes a genuinely empty Saturday would find the whole boutique reported as on
shift. That is the entire reason `rosters` is a row and not a virtual grouping of `roster_assignments`.

### D6 — A draft roster is never authoritative, and drafts are invisible to staff

`published_at IS NULL` ⇒ rule 2 does not fire, rule 3 answers. `GET /manage/shifts/roster` (the builder) is
`ELEVATED`; `GET /manage/shifts/roster/published` (the read-only week) is open to every role and returns
`{published: false, shifts: []}` for an unpublished week — **not** a 404, because "no roster yet" is a real,
renderable answer and a 404 would make the console branch on a status code to say it.

**Rejected — a `status` enum column** (`draft | published`). It would be a second copy of a fact
`published_at` already states, and the pair could disagree; `sos_alerts`' own model comment makes the same
argument about `escalated`/`stalled` (*"`status` is the whole state machine and there is no second copy"*).

### D7 — Publish is idempotent, edits after publish take effect immediately, and there is no unpublish

- `POST /manage/shifts/roster/publish` on an **unpublished** week stamps `published_at` / `published_by`,
  writes `ROSTER_PUBLISHED`, returns the week.
- On an **already published** week whose assignment set is unchanged since the stamp it is a **no-op: no
  write, no audit row** (the shipped no-op rule — F51's per-field audit, F39's D11 save-that-changes-nothing,
  `_transition`'s `changed=False`). It answers 200 with the same payload.
- On an already published week that **has** been edited since, it re-stamps and writes `ROSTER_PUBLISHED`
  with `republish: true` and the counts. This is the brief's "republish", and it is the only thing that
  moves `published_at`.
- **Assignment writes on a published week are allowed and take effect on the next read.** They do **not**
  move `published_at` (D3's failure mode) and they do not require a republish first. The pane shows
  «פורסם ב־…» and, when there are edits after it, one muted line naming that.
- **There is no unpublish** (C5). To stop a roster governing a week the owner removes its assignments,
  which is an honest published statement ("nobody is rostered") rather than a hidden reversion to fallback.

The week already in progress is not special-cased. Publishing a running week is legal and takes effect
immediately — the owner is stating what is true now, and refusing it would leave her nothing but the
same-day override for the rest of the week.

### D8 — The rule label ships on the wire; the client never infers it

`StaffCard.on_shift_source` is one of three literals from the server. The console maps it through a
`Record<OnShiftSource, string>` **with no fallback** — `lib/roles.ts`' `ROLE_LABEL_KEY` argument, and F57's
own recorded near-miss (a two-branch ternary that printed «אחראית משמרת» for every seamstress). A fourth
source is a compile error here rather than a wrong Hebrew word that ships silently.

**Everyone standing at the tablet sees the same label.** Rejected — a staffer-vs-owner split: the board is a
shared floor screen, and two people reading one tablet must not be told different things about the same
card. What *is* role-split is the **control**: the override buttons render for `ELEVATED` only (D13), which
is exactly F39's shape (her own radios; the on-behalf write for elevated).

### D9 — `on_shift` is two new keys on `StaffCard`, never a fourth `StaffCardStatus`

F34's D1 argument, applied to a second orthogonal pair. `status` answers *what she is doing right now*
(occupied / on a break / free); `on_shift` answers *whether she is supposed to be here today*. **Both are
true at once** — a staffer who is off-shift and standing in room 2 is `occupied` and `on_shift: false`, and
that combination is the single most useful thing this feature puts on the board. Folding it into the enum
makes that tuple unrepresentable and breaks `STATUS_BADGE`'s deliberate no-fallback `Record`.

`STAFF_CARD_KEYS` in `test_floor_api.py` goes **8 → 10**, edited by hand. F38's comment says why that is a
feature.

### D10 — Coverage targets are a JSONB column on `shift_templates`, not a third table

```
coverage_targets JSONB NOT NULL DEFAULT '{}'   -- {"sales_assistant": 2, "seamstress": 1}
```

Validated in the service against `StaffRole` (unknown key ⇒ 400) with each value `0..MAX_COVERAGE_TARGET`
(= 20). Keys absent means "no target", which renders as a count with no bar and is **not** the same as `0`
("deliberately nobody"), so the shape must be a sparse map and never a five-element vector.

**Rejected — a `shift_coverage_targets` table.** It would carry a row per (template × role) to express a
number that is edited on the template's own dialog, and it would need its own RLS policy, its own grants,
its own repository and its own cascade when a template is soft-deleted. The JSONB column gets the cascade
for free (delete the template, the targets go with it) and rides F39's existing `PATCH` — which is a **full
replace of all fields** (F39 D2, `UpdateAppointmentTypeRequest`'s rule), so `coverage_targets` becomes the
**sixth** required field and an omitted key can never silently clear it.

**A target edit is NOT a material edit** and invalidates nothing. F39's `is_material_edit` reads
`day_of_week`, `starts_at_time`, `ends_at_time` — a coverage number changes nothing a staffer answered, so
it must not touch her rows. This is a one-line addition to `is_material_edit`'s docstring and **zero** to
its body; stated because "add the new field to the material set" is the reflex.

`tenants.settings` is the wrong home for the same reason F39's D6 chose it for the deadline and not for
this: targets are keyed by a template id, and template ids change.

### D11 — An unavailable staffer is assignable, and the override rides the assignment row

`roster_assignments.override_of_state TEXT NULL`, CHECK against `AvailabilityState`'s three values. Set by
the service **exactly when** the live `staff_availability` row for that (staffer, template, week) says
`unavailable` at assignment time; NULL otherwise. The API requires `acknowledge_override: true` in the body
for that case and answers `409 AVAILABILITY_CONFLICT` without it — so an override is always a second,
deliberate act, never a slip.

**Rejected — refusing the assignment.** *"A real Thursday needs cover regardless of what was submitted on
Sunday"* is the brief's own sentence and it is right. **Rejected — a free-text reason field**: a required
reason nobody fills becomes «cover», and an optional one is empty on every row that matters. Who and when is
`assigned_by` + `created_at` + the `ROSTER_ASSIGNED` audit row, which is what the brief actually asked for.

**Not-answered is not an override.** A staffer with no `staff_availability` row is assignable with no
ceremony (D8's absence-is-not-a-state rule), flagged «טרם הגישה» on the cell. `preferred` and `available`
are both plain assignments — F39 O2 leaves the cap to F40 and **F40 declines to impose one**: a boutique
that wants everyone's preferred shift honoured does not need the platform to count for it.

**A shift with nobody on it is publishable**, flagged and never blocked (pre-decided #40). The builder
shows «חסר איוש» per role and a count; publish never consults it.

### D12 — The shift-manager slot reads `shift_manager_eligible` alone, and there is at most one per shift

`roster_assignments.is_shift_manager BOOLEAN NOT NULL DEFAULT false`, gated by
`staff_users.shift_manager_eligible` and by **nothing else**. Setting it on an ineligible staffer is
`400 NOT_SHIFT_MANAGER_ELIGIBLE`.

**Rejected — implying eligibility from `role IN (owner, shift_manager)`.** F38 shipped the boolean
*specifically* to separate the two claims (`staff_user.py:56-62`, F38 O4 hands the enforcement here), and
deriving one from the other deletes the distinction the column was created to make. The visible cost is
real and accepted: on a fresh boutique **nobody is eligible**, the slot is unfillable, and the pane says so
with a line pointing at «צוות» — one owner action, once, versus a permanent silent conflation.

At most one manager per (roster, template), enforced by a **partial unique index** rather than a service
read-then-write: `(tenant_id, roster_id, shift_template_id) WHERE deleted_at IS NULL AND is_shift_manager`.
Second setter gets `409 SHIFT_MANAGER_SLOT_TAKEN`. The index is a structural guarantee where a lock would
only be a serialisation — F39 D11's argument, and the same `IntegrityError`-retry shape.

### D13 — Authorization: build, publish and the override are all ELEVATED; the published week reads to all

| Act | Gate | Why that gate |
|---|---|---|
| Read the builder (draft or published) | `ELEVATED` | it carries every colleague's submitted state, which is F39's own reason for gating `/shifts/week/submissions` |
| Assign / unassign / set targets | `ELEVATED` | C4 |
| Publish | `ELEVATED` | C4 |
| Same-day override | `ELEVATED`, on `floor/router.py` | it is a statement about somebody else's day |
| Read the **published** week | every role | the floor board already names every colleague; a roster discloses nothing new, and a staffer who cannot see the published roster cannot plan |
| Her own rostered shifts | every role, hers only | rides `MyWeekPanel`'s existing read |

**No self-service on-shift marking.** Rejected explicitly: a staffer marking herself present is an
attendance punch, and the epic's labour-law row puts attendance visibly out of scope. The override control
never renders for a non-elevated role and the route refuses her.

### D14 — Timezone: compare in local wall-clock, half-open, and DST comes out free

`on_shift_at` receives `at` as a UTC `datetime` and converts **once**:

```python
local = at.astimezone(BOUTIQUE_TIMEZONE)
local_date, local_time = local.date(), local.time()
week = current_week_start(local_date)              # F39's helper, imported
day_index = jerusalem_day_index(local_date)        # booking/validation.py, imported
covered = t.starts_at_time <= local_time < t.ends_at_time and t.day_of_week == day_index
```

- **Half-open**, and it is a decision: F39 permits overlapping templates on a weekday (D2), so back-to-back
  shifts 09:00–14:00 and 14:00–20:00 both contain 14:00 under a closed interval and the board would credit
  the outgoing staffer with the incoming shift. `<` on the right end is what makes a handover instantaneous.
- **No wraparound**, because `shift_templates_order_check` bars `ends_at_time <= starts_at_time` — there is
  no overnight shift to split across two dates.
- **DST needs no code.** The direction is instant → local, which is always unambiguous: `astimezone` picks
  exactly one local wall time for any UTC instant, including inside the autumn fold. A 25-hour Jerusalem day
  therefore has one hour whose local clock reads 01:xx twice, and both instants land inside a shift that
  covers 01:00 — correct, the boutique was open for both. A 23-hour day has no local 02:xx at all, so a
  shift spanning it is one real hour shorter — also correct, and the reason **the boutique's wall clock is
  the authority** rather than an elapsed-seconds computation. Storing UTC instants per shift instead would
  need a per-week materialisation and would drift an hour twice a year (F39 D6's argument, second instance).
- The week key comes from the **local** date, so a Saturday 23:30 Jerusalem instant (21:30Z in summer) is
  still in the week that started the previous Sunday, and midnight rollover happens on the boutique's clock.

### D15 — F37's SOS and F42's `assignable` are NOT rewired; the seam ships and adoption is recorded

C2 and C3 give the reasons. What F40 ships instead of the rewiring is the thing that makes it a one-file
change later: `on_shift_at` is a public pure function with no service dependency, and
`RosterAssignmentsRepository.on_shift_staff_ids(session, tenant_id, at)` returns the set in one statement.

Recorded as the upgrade path, in the same shape F37 recorded its Risk 3(a): *extending SOS's role route to
prefer on-shift targets is a `SELECT` over that set plus one distinct sentence on screen, and it is
deliberately not built here.* The word "never" does not belong in that note.

### D16 — No retention policy; the registry stays EIGHT

`rosters` and `roster_assignments` carry a week, a template id, staff ids and two booleans — **no name, no
phone, no free text, nothing a subject request could name.** They are exactly the class F38's spec
enumerated as retained-and-de-identified, naming *"F40's future roster rows"* by name alongside
`fitting_room_assignments` and `sos_alerts`. The `staff_users` SCRUB blanks the person; these rows survive
pointing at an erased row, and that is the answer rather than a gap. The two new `staff_users` columns are
a date and a boolean and stay out of `_scrub_staff_users`' UPDATE.

Growth: 8 staff × 15 shifts × 52 weeks ≈ **6,200 assignment rows/year** per boutique, the same order as
F39's submissions. `test_the_registry_covers_the_eight_classes_with_the_specified_actions` is a **set
equality**, so leaving it at eight is a positive unchanged assertion. `app/privacy/retention.py` is untouched.

### D17 — No new nav row: one pane in F39's section, and the row is renamed

`ShiftsSection.tsx` gains **one** pane, `RosterPane`, between `WeekSubmissionsPane` and `ShiftsDeadlineCard`
— readiness ("can I build?") above the build, configuration below it, which is F39's stated ordering
unchanged. `MyWeekPanel` gains a read-only published block above her radios.

`nav.shifts` changes from «זמינות למשמרות» to «משמרות», because the row now leads to two jobs and the old
label names one. **That is one string in `he.ts`, one in `ar.ts` and one entry in `NAV_LABELS` — the row
count, the `.slice(0, 13)`, the role sets and the ordering assertions are all untouched.**

**Rejected — an eighteenth nav row for the builder.** `Nav.test.tsx` calls a nav row *"five coordinated
edits, not one"*; this feature would pay all five to separate two panes a shift manager opens in the same
minute, and would leave the staffer's own roster stranded in a section whose name no longer covered it.
`SectionKey` stays at seventeen and `GUIDE_STEPS.shifts` grows a third step rather than gaining a key.

---

## Data model

**One migration, head + 1 at build time.** `main` is at `0034`; **F39 holds `0035` and must merge first** —
it is a hard dependency, not a race. Expect `0036` and re-resolve from `alembic heads` immediately before
the rebase, then re-run `test_exactly_one_migration_head`. Raw-SQL house style, `0035_shift_availability.py`
copied in every particular: `_STANDARD` block, `_updated_at_trigger`, `GRANT SELECT, INSERT, UPDATE, DELETE
… TO app_user`, `enable_tenant_rls`. No FK constraints, TEXT not VARCHAR, soft delete, `uuid_generate_v4()`,
partial indexes, forced RLS — each verified against 0035 rather than assumed.

```sql
CREATE TABLE rosters (
    {_STANDARD},
    week_start   DATE NOT NULL,           -- the Jerusalem Sunday (F39 D1's key, same encoding)
    published_at TIMESTAMPTZ,             -- NULL = draft (D6). The ONLY state this table has.
    published_by UUID,                    -- no FK, house rule
    CONSTRAINT rosters_week_start_check   CHECK (EXTRACT(DOW FROM week_start) = 0),
    CONSTRAINT rosters_published_pair_check
        CHECK ((published_at IS NULL) = (published_by IS NULL))
);
CREATE UNIQUE INDEX idx_rosters_week_unique
    ON rosters (tenant_id, week_start) WHERE deleted_at IS NULL;

CREATE TABLE roster_assignments (
    {_STANDARD},
    roster_id         UUID    NOT NULL,   -- no FK
    shift_template_id UUID    NOT NULL,   -- no FK
    staff_user_id     UUID    NOT NULL,   -- no FK
    is_shift_manager  BOOLEAN NOT NULL DEFAULT false,
    assigned_by       UUID    NOT NULL,
    -- The state she had submitted when she was assigned anyway (D11). NULL = no
    -- override. Only 'unavailable' is ever written today; the CHECK is the whole
    -- AvailabilityState set so a later reader is not pinned to one literal.
    override_of_state TEXT,
    CONSTRAINT roster_assignments_override_check
        CHECK (override_of_state IS NULL
               OR override_of_state IN ('available', 'unavailable', 'preferred'))
);
CREATE UNIQUE INDEX idx_roster_assignments_unique
    ON roster_assignments (tenant_id, roster_id, shift_template_id, staff_user_id)
    WHERE deleted_at IS NULL;
-- D12: at most one shift manager per shift, structurally.
CREATE UNIQUE INDEX idx_roster_assignments_manager_unique
    ON roster_assignments (tenant_id, roster_id, shift_template_id)
    WHERE deleted_at IS NULL AND is_shift_manager;
-- The resolver's read and MyWeekPanel's, both.
CREATE INDEX idx_roster_assignments_roster
    ON roster_assignments (tenant_id, roster_id, shift_template_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_roster_assignments_staff
    ON roster_assignments (tenant_id, staff_user_id, roster_id) WHERE deleted_at IS NULL;

ALTER TABLE shift_templates
    ADD COLUMN coverage_targets JSONB NOT NULL DEFAULT '{}'::jsonb;   -- D10

ALTER TABLE staff_users ADD COLUMN on_shift_on       DATE;            -- D4
ALTER TABLE staff_users ADD COLUMN on_shift_override BOOLEAN;
ALTER TABLE staff_users ADD CONSTRAINT staff_users_on_shift_pair_check
    CHECK ((on_shift_on IS NULL) = (on_shift_override IS NULL));
```

All CHECKs and every index are **named** so `pg_get_constraintdef` / `pg_indexes.indexdef` have something to
pin (0023's rule, `test_migrations.py`). No `GRANT` and no `enable_tenant_rls` for the three `ALTER`s —
grants are column-agnostic and RLS is a table property, both already in force (F34 D2 verified this exact
point). `downgrade()` drops both tables and all three columns; **it loses live data** and says so in the
header, 0021/0023/0032/0035's convention.

**Models in the SAME commit** — `app/models/roster.py`, `app/models/roster_assignment.py`, both
`StandardColumns, Base`; `coverage_targets` and the two `staff_users` columns added to their existing
classes; `OnShiftSource(StrEnum)` in `models/constants.py` (**derived**, so no DB CHECK — `StaffCardStatus`'
rule). F40 ships the twin of `test_shift_models_declare_every_column_their_migration_creates` for both new
tables and **extends** `test_staff_user_declares_every_column_the_hr_migration_adds` to read this migration
too — that pair is the only model↔migration parity mechanism in `Backend/tests`, and without it every line
below is an `AttributeError`.

---

## API

`/manage/shifts/roster` — five routes on F39's existing router (second segment `shifts`, so **no
`vite.config.ts` edit**), plus two on `floor/router.py` (second segment `floor`, likewise).

| Route | Gate | Purpose |
|---|---|---|
| `GET /manage/shifts/roster` | `ELEVATED` | `?week_start=` optional (F39's `default_week_start`). The builder: `{week_start, week_end, published_at, published_by_name, edited_since_publish, shifts[], staff[]}` |
| `POST /manage/shifts/roster/assignments` | `ELEVATED` | 201. Body `{week_start, shift_template_id, staff_user_id, is_shift_manager, acknowledge_override}` — **creates the `rosters` row on first write**, in the same transaction |
| `DELETE /manage/shifts/roster/assignments/{assignment_id}` | `ELEVATED` | soft delete |
| `POST /manage/shifts/roster/publish` | `ELEVATED` | body `{week_start}`; idempotent (D7) |
| `GET /manage/shifts/roster/published` | every role | `?week_start=`; `{published: bool, published_at, week_start, week_end, shifts[]}` — never a 404 (D6) |
| `PATCH /manage/shifts/templates/{template_id}` | `ELEVATED` | **existing**; gains required `coverage_targets` (D10) |
| `POST /manage/floor/staff/{staff_id}/on-shift` | `ELEVATED` | body `{on_shift: bool}` — today only, server-dated |
| `DELETE /manage/floor/staff/{staff_id}/on-shift` | `ELEVATED` | clears the pair |
| `GET /manage/floor` | every role | **existing**; `StaffCard` gains `on_shift`, `on_shift_source` |
| `GET /manage/shifts/week` | every role | **existing**; gains `rostered_template_ids[]` + `roster_published` for D17's block |

- `week_start` / `week_end` are `datetime.date` on the wire; `published_at` is an **ISO-8601 UTC instant**.
- The override body carries **no date**. It is always today, computed server-side from `today_jerusalem()`.
  Accepting a date would make rule 1 pre-settable for tomorrow, which is a roster edit wearing an override's
  clothes, and would let a client's clock decide what "today" means.
- Writes use `assert_writable_week`? **No** — F39's forward-only guard is about *submissions*. The roster
  uses `assert_readable_week` (±4 weeks) so a running week can still be edited (D7). Stated because reusing
  the wrong one of two adjacent helpers is the likeliest build error here.
- Error codes: `WEEK_OUT_OF_RANGE` (400, F39's), `AVAILABILITY_CONFLICT` (409),
  `NOT_SHIFT_MANAGER_ELIGIBLE` (400), `SHIFT_MANAGER_SLOT_TAKEN` (409), `COVERAGE_TARGET_INVALID` (400),
  plus the house 404 for an unknown template / staffer / assignment and 403 for the gates.
  `AVAILABILITY_CONFLICT` and `SHIFT_MANAGER_SLOT_TAKEN` are **not** `DomainValidationError` subclasses —
  F39's recorded `ReservationOverlapError` rule: Starlette walks `type(exc).__mro__` and a subclass without
  its own handler answers a quiet, plausible 400 where the console has a specific Hebrew sentence keyed on
  the code.

**Audit** — `audit_log.action` is plain TEXT, no migration:
`ROSTER_ASSIGNED` (`week_start`, template, staff, `is_shift_manager`, `override_of_state`) ·
`ROSTER_UNASSIGNED` · `ROSTER_PUBLISHED` (`week_start`, `assignments`, `shortages`, `republish: bool`) ·
`ON_SHIFT_OVERRIDE_SET` (`staff`, `on_shift_on`, `on_shift`) · `ON_SHIFT_OVERRIDE_CLEARED`.
Coverage targets fold into the **existing** `SHIFT_TEMPLATE_UPDATED` rather than earning a sixth action —
they are written by that route, in that transaction, and a second action for a field of one payload is a
row nobody queries. `details` carry **ids only, never a display name** (`CUSTOMER_UPDATED`'s rule:
`audit_log` has no retention class and platform operators read across tenants). A publish that changes
nothing writes **no row**.

---

## Frontend Changes

### Files

| File | Change |
|---|---|
| `Frontend/apps/manage/src/api.ts` | new wire types + 5 calls; `StaffCard`, `ShiftWeek`, `ShiftTemplate` extended |
| `…/src/components/RosterPane.tsx` | **new** — elevated; the week grid, publish, coverage |
| `…/src/components/RosterCellDialog.tsx` | **new** — assign / unassign / manager slot / override confirm |
| `…/src/components/ShiftsSection.tsx` | one pane inserted after `WeekSubmissionsPane` |
| `…/src/components/MyWeekPanel.tsx` | read-only «המשמרות שלי» block above the radios |
| `…/src/components/ShiftTemplatesPane.tsx` | coverage-target inputs in the template dialog |
| `…/src/components/FloorPanel.tsx` | the on-shift line + rule label on each card; the elevated override control |
| `…/src/lib/onShift.ts` | **new** — `ON_SHIFT_SOURCE_KEY: Record<OnShiftSource, string>` (D8) |
| `…/src/i18n/he.ts` + `…/i18n/ar.ts` | the `shifts.roster.*` and `floor.onShift*` block; `nav.shifts` **renamed**; `ar` untranslated |
| `…/src/lib/guide.ts` | `GUIDE_STEPS.shifts` gains a third step (no new `SectionKey`) |
| `…/src/validation.ts` | `MAX_COVERAGE_TARGET` mirror (parity-tested) |
| `Frontend/e2e/fixtures/manage.ts` | roster route stubs; `floorPayload()` staff gain the two keys |
| `Frontend/e2e/shifts.spec.ts` + `…/floor.spec.ts` | roster + board journeys |

`vite.config.ts` is **unchanged** — both second segments (`shifts`, `floor`) are already proxied.

### Types

```ts
// NEW
export type OnShiftSource = "manual_today" | "roster" | "fallback";

export interface RosterAssignment {
  id: string;
  staff_user_id: string;
  display_name: string;
  role: StaffRole;
  is_shift_manager: boolean;
  override_of_state: AvailabilityState | null;   // non-null = assigned against her answer
}
export interface RosterShift {
  template: ShiftTemplate;
  assignments: RosterAssignment[];
  // Sparse, keyed by StaffRole. A missing key is "no target" and renders as a
  // plain count; 0 is "deliberately nobody" and renders as a target. Not the
  // same thing (D10).
  coverage_targets: Partial<Record<StaffRole, number>>;
  assigned_by_role: Partial<Record<StaffRole, number>>;
}
export interface RosterWeek {
  week_start: string;            // "YYYY-MM-DD", a plain Jerusalem date — never a Date
  week_end: string;
  published_at: string | null;   // ISO-8601 UTC instant; null = draft
  published_by_name: string | null;
  edited_since_publish: boolean;
  shifts: RosterShift[];
  staff: RosterStaffRef[];       // live staffers for the week + her state per template
}
export interface RosterStaffRef {
  id: string; display_name: string; role: StaffRole;
  shift_manager_eligible: boolean;
  states: Record<string, AvailabilityState>;   // by shift_template_id; absent = not answered
}
export interface PublishedRoster {
  published: boolean; published_at: string | null;
  week_start: string; week_end: string; shifts: RosterShift[];
}

// CHANGED — StaffCard (EIGHT keys → TEN)
export interface StaffCard {
  /* … id, display_name, role, status, break_started_at, occupancy,
        photo_url, photo_confirmed_at … */
  on_shift: boolean;             // ADDED
  on_shift_source: OnShiftSource;// ADDED — which of the three rules answered (D8)
}

// CHANGED — ShiftTemplate gains coverage_targets (required on write, D10's full replace)
export interface ShiftTemplateInput { /* … */ coverage_targets: Partial<Record<StaffRole, number>> }

// CHANGED — ShiftWeek, for MyWeekPanel's published block
export interface ShiftWeek { /* … */ roster_published: boolean; rostered_template_ids: string[] }
```

### Component behaviour

**`RosterPane`** (elevated) — owns its own read, its own `Skeleton variant="text" lines={6}`, its own
`role="alert"` + «ניסיון נוסף» retry and its own week pager bounded by `FIRST_OFFSET`/`LAST_OFFSET`. F39's
§1.2 contract, unvaried; no shared "the section failed" state exists and none is added.

- One `<section>` per weekday that has templates, each shift a `Card` with its label, `HH:MM–HH:MM`, its
  assigned staff as removable chips, and a coverage line per role that has a target:
  «{{assigned}} מתוך {{target}}» with a `Badge variant="warning"` «חסר איוש» when short. **Never a colour
  alone** — the word carries the state (`STATUS_BADGE`'s rule, and an a11y requirement).
- **No hour totals anywhere.** No «סה"כ שעות», no weekly sum beside a name, no duration column. F39's design
  §0 binds here and the reason is the epic's labour-law row.
- «הוספה» on a shift opens `RosterCellDialog`: the week's live staff, each with her submitted state as a
  word («זמינה» / «לא זמינה» / «מעדיפה» / «טרם הגישה»), sorted `preferred → available → not answered →
  unavailable`. Picking an unavailable staffer swaps the primary button's label to «שיבוץ בכל זאת» and
  shows the override sentence; that is the `acknowledge_override: true` write.
- The shift-manager slot is one control per shift, populated only from `shift_manager_eligible` staff, with
  the empty-state line pointing at «צוות» when nobody qualifies (D12).
- Header: «טיוטה» or «פורסם ב־…» plus, when `edited_since_publish`, one muted line. One `Button size="md"`
  «פרסום הסידור» / «פרסום מחדש». **No confirm dialog on publish** — it is reversible by editing and
  re-publishing, and F39's Modal-animation finding makes every avoidable dialog an a11y measurement cost.
- **No polling.** A roster changes on human timescales (epic Notes); `App.tsx`'s own argument stands.

**`MyWeekPanel`** (every role) — a read-only block above her radios: «המשמרות שלי» listing the shifts she is
rostered on for the displayed week, or «סידור העבודה לשבוע הזה טרם פורסם.» when `roster_published` is false,
or «לא שובצת למשמרות בשבוע הזה.» when it is true and the list is empty. Those three states are distinct
sentences because D5 says they are distinct facts.

**`FloorPanel`** — each card gains one line under the status badge: the on-shift word plus the rule label,
e.g. «במשמרת · לפי סידור העבודה». For an elevated viewer, two `Button size="md"` controls beside the break
toggle: «סימון שאינה במשמרת» / «סימון במשמרת» (whichever contradicts the current answer) and, when an
override is live, «ביטול הסימון הידני». Non-elevated sees the line and no control (D13).
The card's photo pin (`(id, photo_confirmed_at)`) is untouched — the two new keys are booleans/enums and
change nothing about the ~5 s tick's image handling.

### Copy (Hebrew-first; **no exclamation marks**, pre-decided #5, asserted by `i18n.test.ts`)

| Key | Hebrew |
|---|---|
| `nav.shifts` | משמרות  *(renamed from «זמינות למשמרות», D17)* |
| `floor.onShift` | במשמרת |
| `floor.offShift` | לא במשמרת |
| `floor.onShiftManualToday` | נקבע ידנית להיום |
| `floor.onShiftRoster` | לפי סידור העבודה |
| `floor.onShiftNoRoster` | אין סידור עבודה לשבוע הזה |
| `floor.markOnShift` | סימון במשמרת |
| `floor.markOffShift` | סימון שאינה במשמרת |
| `floor.clearOnShiftOverride` | ביטול הסימון הידני |
| `floor.onShiftOverrideNote` | הסימון הידני תקף להיום בלבד ומתאפס בחצות. |
| `shifts.rosterHeading` | סידור עבודה |
| `shifts.rosterDraft` | טיוטה. הסידור אינו גלוי לצוות ואינו קובע מי במשמרת. |
| `shifts.rosterPublished` | פורסם ב־{{date}} בשעה {{time}} על ידי {{name}}. |
| `shifts.rosterEditedSincePublish` | בוצעו שינויים מאז הפרסום. הם כבר בתוקף בלוח הקומה. |
| `shifts.publish` | פרסום הסידור |
| `shifts.republish` | פרסום מחדש |
| `shifts.addToShift` | הוספה למשמרת |
| `shifts.assignAnyway` | שיבוץ בכל זאת |
| `shifts.overrideWarning` | {{name}} סימנה שאינה זמינה במשמרת הזו. השיבוץ יירשם כחריגה. |
| `shifts.overrideBadge` | שובצה בחריגה |
| `shifts.coverage` | {{assigned}} מתוך {{target}} |
| `shifts.coverageShort` | חסר איוש |
| `shifts.emptyShift` | עדיין לא שובצה אף אחת למשמרת הזו. |
| `shifts.managerSlot` | אחראית משמרת |
| `shifts.managerNoneEligible` | אף אחת מהצוות אינה מסומנת כמתאימה לניהול משמרת. אפשר לסמן במסך צוות. |
| `shifts.coverageTargets` | יעדי איוש |
| `shifts.myRosterHeading` | המשמרות שלי |
| `shifts.myRosterNone` | לא שובצת למשמרות בשבוע הזה. |
| `shifts.myRosterUnpublished` | סידור העבודה לשבוע הזה טרם פורסם. |
| `shifts.errors.availabilityConflict` | {{name}} סימנה שאינה זמינה. צריך לאשר את החריגה. |
| `shifts.errors.notEligible` | אפשר לשבץ כאחראית משמרת רק מי שסומנה כמתאימה לכך. |
| `shifts.errors.managerSlotTaken` | כבר שובצה אחראית משמרת למשמרת הזו. |
| `shifts.errors.coverageTargetInvalid` | יעד האיוש חייב להיות מספר שלם בין 0 ל־20. |
| `guide.shifts.3` | כאן בונים את סידור העבודה לשבוע ומפרסמים אותו לצוות. |

`ar.ts` gets every key with the approved Hebrew standing in, untranslated (Q3 / pre-decided #47). The four
new `shifts.errors.*` codes are added to `MyWeekPanel`/`RosterPane`'s `MAPPED_CODES` **by hand** —
`SPEC_ERROR_CODES` is a Python set checked against Python and cannot catch an unmapped code (F39's own note).

### Accessibility floor — a **legal** gate (IS 5568 / WCAG 2.0 AA), not a preference

axe **zero violations** on the roster pane (draft and published), on `RosterCellDialog`, on `MyWeekPanel`'s
new block and on the floor board with each of the three rule labels. Every touch target ≥ 44 px:
`Button size="md"` only — `size="sm"` is 36 px and is forbidden throughout (F-W1). Settle the `Modal` open
animation before measuring (the 0032-era finding: a compliant 44 px control measures 42.68 px mid-transition;
settle, never lower the floor). RTL throughout; every numeral run and time range in `<bdi dir="ltr">`, human
names in a bare `<bdi>`. Shortage is **never colour-only** — «חסר איוש» is a word. Each shift `Card` is a
`<section>` with an `h3` naming the shift, so the grid is navigable by heading and not only by tabbing
through chips.

---

## Test strategy

**Fast lane** (no Docker, no Postgres, no Node — `make test` points this lane at a closed port):

- **`test_shifts_resolver.py` — the three-rule matrix, exhaustively, and this is the highest-value file in
  the feature.** `on_shift_at` is pure, so every ordered pair is a parametrised case with no fixtures:

  | override | roster | expected |
  |---|---|---|
  | today, `true` | published, rostered | `(True, MANUAL_TODAY)` |
  | today, `true` | published, not rostered | `(True, MANUAL_TODAY)` |
  | today, `false` | published, rostered | `(False, MANUAL_TODAY)` ← **the sick call; the case the feature exists for** |
  | today, `false` | published, not rostered | `(False, MANUAL_TODAY)` |
  | today, `true` | **no published roster** | `(True, MANUAL_TODAY)` |
  | today, `false` | **no published roster** | `(False, MANUAL_TODAY)` ← rule 1 must work in a boutique that never publishes |
  | today, `true`/`false` | **draft only** | `(override, MANUAL_TODAY)` |
  | **yesterday** (stale) | published, rostered | `(True, ROSTER)` |
  | **yesterday** (stale) | published, not rostered | `(False, ROSTER)` |
  | **yesterday** (stale) | no published roster | `(True, FALLBACK)` |
  | **tomorrow** (pre-dated) | published, rostered | `(True, ROSTER)` — a future date is never consulted |
  | none | published, rostered | `(True, ROSTER)` |
  | none | published, not rostered | `(False, ROSTER)` |
  | none | **draft with assignments** | `(True, FALLBACK)` ← **a draft is never authoritative (D6)** |
  | none | published, **zero assignments in the whole week** | `(False, ROSTER)` ← not the same as no roster (D5) |
  | none | no roster row at all | `(True, FALLBACK)` |

  Plus, on the same module: the **half-open boundary** at exactly `starts_at_time` (in) and exactly
  `ends_at_time` (out); two overlapping templates both covering an instant (OR, one answer); a template on a
  different `day_of_week`; **the DST pair** — the same wall-clock shift resolved from a January instant and a
  July instant, and an instant inside the autumn fold falling in a shift that covers that local hour.
- `test_shifts_validation.py` — `coverage_targets` shape (unknown role key, negative, over `MAX_COVERAGE_TARGET`,
  non-integer, `true` coerced), and that `is_material_edit` is **unchanged** by a targets-only edit.
- `test_shifts_service.py` — publish idempotence (second call writes nothing); republish after an edit
  stamps and audits; assigning an `unavailable` staffer without `acknowledge_override` is 409 and with it
  writes `override_of_state`; the eligibility gate refuses a non-eligible staffer and admits an eligible
  `seamstress`; `role == shift_manager` with the column false is **refused** (D12's whole point); the
  elevated gate matrix over all five roles.
- `test_floor_service.py` — the four resolver inputs are gathered from the row and the two reads and nothing
  else; a card is never dropped (D1: assert the returned staff count equals `list_live`'s for every rule).
- Walkers, all updated **in this feature's commits**: `test_staff_role_gating.py` (five new tuples —
  `ROSTER_PUBLISHED_READ` into all three `NON_ELEVATED_REACH` rows; the four builder routes and the two
  override routes into `SHIFTS_ELEVATED` / `FLOOR_OPEN`'s elevated set and into **nobody's** reach row;
  nothing enters `OWNER_ONLY`), `test_audit_coverage.py` (all seven mutating routes resolve as audited,
  **none** exempt), `test_cross_tenant_walker.py` (the pinned pair — F39 leaves it at `(70, 68)`; re-read it
  at build time rather than trusting this line), `test_frontend_constant_parity.py` (`MAX_COVERAGE_TARGET`),
  `test_spa_serving.py` (**unchanged, and assert so** — no new second path segment).
- Frontend (vitest/jsdom) — `RosterPane.test.tsx` (draft vs published header, coverage counts and the
  shortage word, publish button label flip, week paging bounds, load-failure alert + retry),
  `RosterCellDialog.test.tsx` (state sort order, the override confirm's copy and payload, the manager slot's
  eligible-only list, the nobody-eligible empty state), `MyWeekPanel.test.tsx` (the three published-block
  states), `FloorPanel.test.tsx` (**all three rule labels render**; the override controls appear only for
  elevated; a card with `on_shift: false` is still rendered — the D1 regression guard), `Nav.test.tsx` (the
  renamed label, and that the counts and slices did **not** move), `i18n.test.ts` (every new key resolves,
  `ar` parity, **zero exclamation marks**).

**db-marked** (CI-only — there is no local Docker; a `not db` test that dials a real Postgres is F21's
shipped false-green class):
- `test_migrations.py` — all four new CHECK definitions and all five indexes pinned by deparsed literal;
  the `staff_users` pair CHECK; `coverage_targets`' NOT NULL + default; up/down round-trip;
  `test_exactly_one_migration_head` **after** the rebase renumber.
- `test_roster_isolation.py` — RLS on both new tables, house suite pattern.
- `test_roster_db.py` — assign → publish → edit → republish with its audit rows (details carry **no** display
  name); the first assignment creates the `rosters` row in the same transaction; **two concurrent
  shift-manager writes** (NullPool + `asyncio.gather`, the F13 precedent) leave exactly one live row and the
  loser gets 409 from the partial unique index, not from a read; the same for two concurrent identical
  assignments; a published week with zero assignments answers `(False, ROSTER)` for every staffer while a
  week with no row answers `(True, FALLBACK)`; a soft-deleted template's assignments stop resolving; an
  offboarded staffer is absent from the builder's staff list and her id is a 404 on assign; a `week_start`
  that is not a Sunday is refused **by the DB CHECK** even with the service guard removed.
- `test_floor_api_db.py` (or the shipped floor db suite) — the board renders all three rule labels off real
  rows, and the override survives exactly one Jerusalem day: set at 23:59 local, still live; the same row
  read at 00:01 local the next day resolves through rule 2 or 3 with **no writer having run**.
- `test_retention_policies.py` — the registry assertion stays **eight** (a positive unchanged assertion).

**s3-marked**: none — this feature touches no storage.

**e2e (Playwright + axe)** — `shifts.spec.ts` gains: an owner sets a coverage target, assigns three staff
including one who marked unavailable (confirming the override), fills the manager slot, publishes, and the
header flips; a seamstress opens «משמרות» and reads «המשמרות שלי». `floor.spec.ts`: the board shows the
roster label; the owner marks a rostered staffer off for today and the label and the word both change on the
next tick. **axe zero violations** on each, RTL, 44 px targets measured after animations settle.

---

## Stale-brief traps resolved

1. **"F31 already gives the owner a manual way to mark who is on shift"** (epic Why, Feature 40 brief,
   Success Criteria and the LOOP-STATE F40 note) — **there is no such mechanism.** No column, no route, no
   toggle. F31 shipped the role member and `/manage` gating. What is demoted is *liveness*; rule 3 resolves
   to today's exact behaviour, so a non-publishing boutique sees no change. → **C1 / D1**
2. **"F31's manual toggle is not deleted … and it must be timestamped so rule 1 can tell 'set today, after
   publish' from 'left on since last month'"** — the toggle F40 builds is new, and it is scoped to a
   Jerusalem DATE rather than timestamped, which delivers the same guarantee with no clock comparison and no
   expiry writer. → **D3 / D4**
3. **"a same-day manual flag set after the roster was published wins"** — the `published_at` comparison is
   rejected: an edit to Thursday would revoke an unrelated override on Sunday. Date-scoping is the whole
   freshness rule. → **D3**
4. **"F37's role-targeted SOS paging" as a consumer** — `sos_alerts` has no role column; NULL means the
   two-member elevated audience, and the only reachability probe reads a live *session*, which is a better
   proxy than a roster. Not rewired; the seam and the upgrade path are recorded. → **C2 / D15**
5. **"F42's seamstress daily availability" as a consumer** — F42 shipped with its F40 dep explicitly dropped
   and `assignable` derived from role + liveness. Not rewired. → **C3 / D15**
6. **"A published roster silently widens who gets paged" (epic Risk)** — that risk is created by wiring the
   roster into SOS, which F40 declines. The residual risk it names (a manager who neither updates the roster
   nor flips the flag) survives on the board's label only, which is the correct place for it. → **C2**
7. **`deps: [F34]`** — F34 is the bookings board; the staff cards are F57's `FloorPanel` on `GET /manage/floor`.
   Building against F34 touches the wrong file. Same error class as F60's corrected dep line. → **C6**
8. **"the owner … assigns … and publishes"** — narrowed against the shipped `ELEVATED_ROLES` predicate, which
   is what every other floor capability uses. A shift manager may build and publish. → **C4 / D13**
9. **"Publish makes the week … immutable except by republish"** — no unpublish and no edit lock are built;
   publish is idempotent, edits land immediately, and the honesty comes from `published_at` plus the board
   label. → **C5 / D7**
10. **"coverage targets per (weekday shift template × role)" implies a table** — one JSONB column on
    `shift_templates` gets the cascade, the dialog and the full-replace semantics for free. → **D10**
11. **Retention reflex** — an E8 feature storing ids, dates and booleans. The registry stays **EIGHT**,
    counted from `POLICIES` rather than assumed, asserted by an unchanged set equality. → **D16**
12. **Migration numbering** — the epic and LOOP-STATE both carry stale heads. `main` is at **0034** (F26's
    platform invites merged), F39 holds **0035** on its branch. Resolve from `alembic heads` immediately
    before the rebase, not from this document.
13. **"the roster grid … self-approves under Q2's familiar-screen rule"** — it does, and the epic's own
    escalation clause stands: if `design-critic` rejects the pane twice, treat it as novel and bring the user
    a prototype rather than iterating a third time.

---

## Gate 1 questions

**None.** F40 self-approves under Q1. Every question a first draft would have escalated was answerable from
shipped code or a recorded decision, and was answered rather than deferred:

- *What does F40 replace, and who calls it today?* → **Nothing, and nobody.** Verified by grep and by reading
  `FloorService.read`, `SosService.raise`, `SeamstressRef.from_row`. The cutover is additive. (C1)
- *Does the board filter to on-shift staff?* → **No.** `card_status`' own recorded principle about the screen
  lying about something visible settles it. (D1)
- *Owner-only publish, or elevated?* → resolved against the shipped `ELEVATED_ROLES` / `OWNER_ONLY` split.
  **Elevated.** (C4 / D13)
- *May an owner or a `shift_manager` fill the manager slot without `shift_manager_eligible`?* → F38 O4 hands
  this here. **No** — the column alone, or the distinction it exists for is deleted. (D12)
- *Is a staffer rostered against her `unavailable` refused?* → **Allowed, with an explicit acknowledgement and
  the state recorded on the row.** The brief's own sentence about a real Thursday. (D11)
- *Does this need a retention policy?* → resolved against the shipped registry and F38's enumeration of
  retained rows, which names F40's roster rows by name. **No.** (D16)

## Open questions (recorded, non-blocking)

- **O1 — the scope reduction in D15 is the one thing worth a user overrule.** The epic's fourth success
  criterion names F34, F37 and F42 as consumers; F40 wires **one** (the floor board) and records the other
  two as declined-with-reasons. If the user wants the SOS half, it is a `SELECT` over
  `on_shift_staff_ids` plus one Hebrew sentence — a small follow-up, and deliberately not smuggled in here.
- **O2 — the nav rename** «זמינות למשמרות» → «משמרות» edits copy F39's design gate approved days ago. One
  string, reversible, flagged for the copy pass rather than assumed.
- **O3 — `MAX_COVERAGE_TARGET = 20`** is a guard against a fat finger, not a product rule. It is a constant,
  not a migration.
- **O4 — copy-last-week** is the obvious follow-up (epic OUT, and F39 O4 said the same about submissions).
  Every column it needs exists; it is a service method and a button.
- **O5 — no staff notification on publish.** F39 declined the deadline nudge for the cost of one SMS per
  staffer per week; the same arithmetic applies, and `staff_notifications` (F35) is the cheaper channel if
  the pilot asks. Recorded so the next reader finds the argument rather than a silence.
- **O6 — a stale published roster is the epic's honest residual risk** and F40 does not close it: a manager
  who neither edits the roster nor sets an override leaves the board confidently wrong. The label is the
  mitigation (a reader can at least see *why* the board says what it says), and the pilot should be watched
  for it.
