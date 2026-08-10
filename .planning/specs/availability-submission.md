# Feature 39 — Staff availability submission: shift templates + the weekly Sunday-start window

**Epic**: E8 · **Size**: M/L · **Deps**: F38 (merged, PR #55) · F31 · F12 · F7 · F9 · ~~F11~~ (see C1)
**Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals (Q1).**

F39 self-approves. Q1's stop-list is *payments, refunds, privacy-law **text**, tenant billing*; F39 authors
none of it. It stores no new personal data at all (C5), adds no legal wording, and touches no money path.
The one thing worth naming up front is that this is **not** an hours-worked record and must never become
one — the epic's own labour-law risk row binds here, and a later feature reading these rows as attendance
is a review-blocking drift.

---

## Verified against the codebase (2026-08-10, `main` @ `b43fb63`)

| Claim | Reality |
|---|---|
| Opening hours | `Backend/app/models/availability.py` — `AvailabilityRule(tenant_id, day_of_week INT, open_time TIME, close_time TIME, capacity INT)` + `StandardColumns`. **Multiple windows per day**, non-overlap enforced in the service, `0=Sunday … 6=Saturday`. `AvailabilityException` is a per-date override, unrelated here. |
| Hours UI | `Frontend/apps/manage/src/components/HoursSection.tsx` — whole-week replace through `PUT /manage/availability/rules`, `DAY_NAMES` = the seven Hebrew day names at indices 0–6 |
| Week index | `app/booking/validation.py::jerusalem_day_index` — `(date.weekday() + 1) % 7`, and its docstring names `packages/ui/src/lib/hours.ts` as the FE twin, pinned by `test_frontend_constant_parity.py` |
| Boutique clock | `app/storefront/validation.py:40,86` — `BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")`, `today_jerusalem()` |
| Tenant settings | `tenants.settings JSONB NOT NULL DEFAULT '{}'`; one atomic `settings = settings \|\| :patch::jsonb` in `TenantsRepository.merge_settings` — four keys today (`profile`, `atelier`, `privacy` whole-block; `toggles` deep-merged). `BoutiqueSettingsService.update_settings` validates then merges then audits |
| Staff row | `app/models/staff_user.py` — F38's eleven columns are live, incl. `phone` (contact only), `start_date`, `last_day`, `shift_manager_eligible`, `scrubbed_at`, six photo columns |
| Staff auth | email + password, `/manage/auth/login`, session cookie; `AuthService.resolve_session` re-reads `staff_users` per request and `by_id` filters `deleted_at IS NULL` |
| Role predicate | `StaffRole` = `owner, shift_manager, reception, sales_assistant, seamstress`; `require_role(*allowed)` composes by **intersection** and can only NARROW; `floor/service.py:101` `ELEVATED_ROLES = {owner, shift_manager}`; `floor/service.py:1924` is the shipped self-or-elevated guard, raising `NotAuthorizedError` (403) |
| All-role router | `app/floor/router.py` — `prefix="/manage"`, `dependencies=[_no_store, require_role(*StaffRole)]`, per-route `ELEVATED` narrowing. **The precedent this feature copies wholesale.** |
| Retention registry | `app/privacy/retention.py` `POLICIES` — **EIGHT** since F38 (`otp_codes, sessions, queue_tickets, waitlist_entries, message_log, bookings, customers, staff_users`). `test_the_registry_covers_the_eight_classes_…` is a **set equality** |
| Audit action column | `audit_log.action` is plain TEXT with **no CHECK** (`0003_auth.py:71-79`). This is the eleventh feature block to rely on it; no migration |
| Migration head | `0032_staff_hr_directory.py` on `main`. **F26 holds `0034_platform_invites.py` in `.worktrees/invite-signup`, unmerged.** Build at head+1 **at build time**, renumber at rebase (`.memory/parallel-alembic-numbering`; 0032's own header is the case study) |
| Walkers | `test_cross_tenant_walker.py` (`(67, 65)` pinned, `MODULE_WALK_FLOOR`, `_MODULE_BY_PREFIX`), `test_audit_coverage.py` (`UNAUDITED_BY_DECISION`), `test_staff_role_gating.py` (`OWNER_ONLY`, `NON_ELEVATED_REACH`, `FLOOR_OPEN`/`ATELIER_OPEN`), `test_spa_serving.py` (vite proxy alternation set-equality) |
| Nav counts | `Nav.test.tsx` — owner **15**, shift manager `.slice(0, 12)`, `NAV_LABELS` length **15**; its own comment: *"a nav row is five coordinated edits, not one"* |
| Touch floor | `packages/ui/src/components/Button.tsx` — `sm: min-h-9` (36 px) **fails** the 44 px floor; `md: min-h-11` is the default and the only legal size here |

---

## Conflicts recorded (the brief predates shipped reality)

**C1 — the phone-first flow does not exist and must not be built.** The brief says the staffer
*"authenticates with phone + SMS OTP through F11's existing primitive"* and lands *"on the phone they
already sign in with"*, and LOOP-STATE lists **F11 as a dependency**. All of that died with F31 (Interview
Q11 overridden 2026-07-30) and F38 settled it in writing (C1, and `staff_user.py:44-46`: *"nothing in
app/auth reads this column"*). F39 collects availability from an **already signed-in staffer** through the
unchanged session cookie, on the existing manage console. **F11 is a nominal dep this feature does not
use** — no OTP route, no `notifications` import, no rate limiter. The epic's *"Production staff login is
externally blocked"* risk row therefore does **not** apply to F39 either: staff login shipped and works.

**C2 — "the deadline is a tenant setting" survives; F20's retention ruling does not reach it.** F38's C4
overrode the brief in the other direction for the retention clock, on F20's shipped words
(`config.py:294-296`): *"a boutique may not choose its own retention for a duty the platform enforces on
its behalf."* That argument is **scoped to a legal duty the platform discharges** and to values with a
counsel confirmation pending. A submission deadline has neither: no regulator, no counsel, no DB CHECK
twin and no legal duty. The same paragraph's stated reason for keeping product policy out of `Settings`
is *"drift between an env var and a DB CHECK or a frontend constant"* — which is an argument **for**
putting this in `tenants.settings`. Pre-decided #36 and #19 both land there. **Resolved: tenant setting,
in `tenants.settings` under a new top-level `scheduling` key, through F7's atomic merge (D6).**

**C3 — "the owner can reopen a locked week" is over-built and is not shipped.** The brief's mechanism
needs per-week reopen state (a row, a clock, a who, an expiry) to express something the shipped role model
already expresses for free: an elevated actor may act on any staffer. F39 ships the lock for the staffer
and **no reopen at all** — the owner or shift manager records on her behalf, at any time before the week
starts, with `recorded_by` on the row and an audit entry (D5). The brief's intent («the owner is never
stuck») holds exactly; the state does not exist to drift.

**C4 — F38's O3 rests on a false premise, and it changes nothing.** O3 defers staff self-service photo
upload to *"F39, which is the first screen a non-owner staffer will actually open."* It is not: `App.tsx`
NAV already gives `floor` to reception / sales assistants / seamstresses and `atelier` to seamstresses,
both shipped. F39 is the fourth such screen, not the first. **O3 stays deferred anyway** — a photo upload
is F38's surface, not this one's, and F39 adds no staff-editable profile field.

**C5 — this feature stores no new personal data, and the registry stays EIGHT.** See D9. Stated as a
conflict because the brief's own success criteria put F39 inside an epic whose other two features are
PII-heavy, and the reflex is to append a ninth policy.

---

## IN

1. **`shift_templates`** — owner-defined, per weekday, mutable in place, soft-deleted. Created by an
   explicit one-time **seed from `availability_rules`** (D3) and then split / renamed / removed by hand.
2. **`staff_availability`** — one row per (staffer × template × week), state
   `available | unavailable | preferred`. Absence of a row **is** "not answered" (D8).
3. **The weekly window**, Sunday-start, Jerusalem, keyed by a DATE (D1); a deadline resolved from a tenant
   setting against the target week (D6); a hard lock for the staffer past it (D5).
4. **The staffer's screen** — one column, one save, every role, her own week only.
5. **The owner's two panes** — the template editor, and the roster-readiness read (who has not submitted).

## OUT

Standing / recurring availability ("never Mondays") · time-off and vacation requests with approval ·
partial-shift availability (an hour inside a template) · shift swaps between staff · automated deadline
nudges (the epic's own OUT: a `scheduled_messages` row with a widened `kind`, one SMS per staffer per
week, not on by default) · **any roster, assignment, coverage target or publish** — that is F40 and this
spec builds none of it · overnight shifts (D2 ceiling) · hours worked, attendance, pay, any Hours of Work
and Rest Law validation (epic risk: *must stay visibly out*) · a reusable segmented-control component in
`@boutique/ui` (D13) · polling on any surface here.

---

## Decisions

### D1 — The week is keyed by a DATE: the Jerusalem Sunday

`staff_availability.week_start DATE NOT NULL`, holding the calendar date of the **Sunday that opens the
week, in Asia/Jerusalem**, with a named CHECK `EXTRACT(DOW FROM week_start) = 0` (Postgres DOW is
`0=Sunday`, the same encoding `availability_rules.day_of_week` already uses).

**Why a DATE and not a TIMESTAMPTZ, given this repo's TIMESTAMPTZ-everywhere rule.** That rule governs
**instants** — a thing that happened at a moment. A week key is not an instant; it names a page of the
boutique's calendar, and the shipped type for that here is DATE, three times over: `dress_reservations.
starts_on/ends_on` (F28 D2: *"a rental leaves and returns on calendar DAYS"*), `waitlist_entries.day`, and
`staff_users.last_day` (F38: *"an instant would make the boundary depend on what o'clock somebody pressed
the button"*).

**And a UTC-midnight instant would be the wrong day, twice.** Jerusalem is **UTC+2 in winter and UTC+3 in
summer**. `2026-11-08T00:00:00Z` is 02:00 on the 8th locally; `2026-06-07T00:00:00Z` is 03:00 on the 7th
— so the *same* civil Sunday keys to two different offsets across the year, any client computing the key
from a local midnight produces a different instant from the server's, and an equality join on the key
silently misses. A DATE has no offset to get wrong.

The key is **always computed server-side** from `today_jerusalem()`; a client may *name* a week
(`?week_start=`) but the server validates the Sunday-ness and the window and never trusts the arithmetic.
`jerusalem_day_index` is imported from `app/booking/validation.py`, never re-derived.

**Window** — `SUBMISSION_WEEK_WINDOW_WEEKS = 4`. Reads accept `current_week_start ± 4 weeks`; anything
outside is `400 WEEK_OUT_OF_RANGE`. Writes additionally require `week_start > current_week_start` — the
current week has begun and F40 publishes before a week starts, so recording availability into a running
week is F40's roster-edit problem and not this feature's. Rejected: implying "next week" with no parameter
at all — "next" changes meaning at Saturday midnight and a browser on a New York clock disagrees with the
server for part of every day, which is `jerusalem.ts`'s whole reason for existing.

### D2 — `shift_templates` are mutable in place, never versioned

Four editable fields: `day_of_week`, `label`, `starts_at_time`, `ends_at_time` (plus `sort_order`). A
PATCH is a **full replace of all five** — `UpdateAppointmentTypeRequest`'s shipped rule, so an omitted key
can never silently clear a value.

**Not versioned.** Versioning forces every reader — including all of F40 — to resolve templates *as of* a
week, and hands the owner a growing pile of dead rows for every typo she fixes. Rejected.

**Overlapping templates on one weekday are LEGAL**, deliberately, and this is the one place F39 departs
from `validate_weekly_rules`' shape. A morning 09:00–14:00 and an afternoon 13:00–20:00 sharing the
changeover hour is an ordinary split-shift, and refusing it makes the owner fudge her real times. What the
platform *does* bound is the count: `MAX_TEMPLATES_PER_DAY = 6` (a thumb-sized list on a phone) and
`MAX_TEMPLATES = 42`. Coverage arithmetic over overlapping shifts is F40's problem to state, not this
feature's to prevent.

`ends_at_time > starts_at_time`, a named CHECK — so **no overnight shift**. A bridal boutique does not run
one. `# ponytail: an overnight template needs a crosses_midnight flag or a duration column; nothing here
blocks adding it.`

### D3 — Seeding is an explicit, one-time, refusable action

`POST /manage/shifts/templates/seed` writes **one template per live `availability_rules` row**:
`day_of_week`, `open_time → starts_at_time`, `close_time → ends_at_time`, auto-label «ראשון 09:00–17:00»
(the day name from the shipped `DAY_NAMES`, times `HH:MM`), `sort_order` by `open_time`.

**`capacity` is deliberately dropped.** It is the slot engine's parallel-appointments number
(`availability.py:21`), not a headcount — copying it into a shift would make a "capacity 2" window read as
"two staff needed", which is a coverage target and therefore F40's, and would be wrong the day a boutique
takes two fittings with one assistant.

Concretely, then, *"pre-filled from opening hours"* means: a boutique whose Sunday is one 09:00–17:00
window gets **one full-day Sunday shift** it may then split; a boutique that already entered a split
Thursday (10:00–14:00 and 16:00–21:00) gets **two Thursday shifts** for free. **Saturday has no rule, so
it gets no template and nothing to submit** — as an emergent consequence of the tenant's own data, never
as a hardcoded Shabbat rule.

**It refuses if any live template exists** (`409 TEMPLATES_ALREADY_SEEDED`) and it is never triggered by a
read. A re-sync that silently destroyed the owner's splits is the failure this refusal exists to prevent;
a read path that writes is what F37's D6 rejected on principle.

### D4 — A material template edit INVALIDATES future submissions against it

Editing `day_of_week`, `starts_at_time` or `ends_at_time`, or deleting the template, **soft-deletes every
live `staff_availability` row for that template in every week `> current_week_start`**, in the same
transaction. Editing only `label` or `sort_order` invalidates nothing.

Rejected — silent re-pointing: a staffer who answered "available, Thursday morning" would find herself
holding an answer to "available, Thursday **night**" that she never gave, on a surface whose entire
content is what she said. Rejected — refusing the edit while submissions exist: the owner would have to
delete other people's answers by hand to fix her own typo.

The invalidation is **visible, not silent**: the owner's confirm dialog states the count before she
commits, the roster-readiness list repopulates with «טרם הגישה», and `SHIFT_TEMPLATE_UPDATED` /
`_DELETED` carry `invalidated_submissions` in `details`. Past and current weeks are untouched — they are
history, and F40 may already have published off them.

### D5 — The deadline hard-locks the staffer; there is no reopen

Past the deadline for a week, a staffer's own write is `409 SUBMISSION_CLOSED`. **An elevated actor
(`owner` or `shift_manager`) is not subject to the deadline at all** and may record for any staffer for
any writable week (D1's window). That write sets `staff_availability.recorded_by = actor.id`; a staffer
recording her own is `recorded_by IS NULL`.

This is C3's resolution. The audit row carries `after_deadline: true` and `on_behalf_of`, so «who recorded
this, for whom, past the deadline» is one `WHERE action = 'availability_submitted'` and not a JSONB walk.
Her own screen renders «נרשם על ידי {{name}}.» on any row she did not enter — the same honesty
`fitting_room_assignments`' handover `from` buys, and the reason `recorded_by` is a column and not a
derived guess.

The lock is a **pure read-time predicate** over the tenant setting and the target week. No per-week state
exists, so none can drift, and `locked` on the week payload is computed by the same helper the write path
calls (`deposit_due`'s rule: the page a person reads and the flow she then enters cannot disagree).

### D6 — The deadline is `tenants.settings.scheduling`, whole-block, through F7's merge

```jsonc
{"scheduling": {"submission_deadline_day_of_week": 3, "submission_deadline_time": "18:00"}}
```

A **weekday + a local time**, never a stored instant — the `user_preferences` shape `TIMEZONE.md`
prescribes and for its exact reason: "18:00 Wednesday" is `16:00Z` in winter and `15:00Z` in summer, so a
stored UTC value drifts an hour twice a year. The instant is computed per week:
`ZonedDateTime`-equivalent — `datetime.combine(deadline_date, deadline_time, tzinfo=BOUTIQUE_TIMEZONE)`,
where `deadline_date` is the named weekday in the week **preceding** `week_start`.

Default `(3, "18:00")` = **Wednesday 18:00**, which leaves Thursday–Saturday to build the roster before
Sunday. A guess at the pilot's norm, recorded as O1.

Mechanics, following the shipped four keys exactly:
- `SchedulingSettingsUpdate(ForbidExtraModel)` with **both fields REQUIRED, no defaults** —
  `AtelierSettingsUpdate`'s rule, and load-bearing for its reason: `||` merges at the **top level only**,
  so a partial `scheduling` object replaces the whole key and deletes what it did not name. `StrictInt`
  for the day, or `{"submission_deadline_day_of_week": true}` coerces to `1` before any validator runs.
- `merge_settings` gains a fifth kwarg `scheduling=`, in the **whole-block-replace** branch beside
  `profile`/`atelier`/`privacy`. It does **not** get `toggles`' deep merge: there is one writer, one
  dialog, one save.
- `validate_scheduling_settings` in `boutique/validation.py` — unknown keys refused, day `0..6`, time
  matching `^([01]\d|2[0-3]):[0-5]\d$`.
- `SettingsResponse.scheduling` ships **default-complete** (`{**SCHEDULING_DEFAULTS, **stored}`), the
  `toggles` D3 shape, so neither the console nor the lock predicate needs `?? default` anywhere.
- Audit: `AuditAction.SCHEDULING_SETTINGS_UPDATED`, written by the existing shared
  `_record_settings_audit` with the whole new block (`ATELIER_SETTINGS_UPDATED`'s rule — it is always
  written whole). Boutique configuration; no personal data.

### D7 — One new module, one new router, `require_role(*StaffRole)` with per-route narrowing

`app/shifts/` (`router.py`, `service.py`, `schemas.py`, `validation.py`), a **sixth router on `/manage`**,
mounted after `staff_router` in `create_app()`.

A new module is **structural, not stylistic** — `floor/router.py:73-78` states the rule: `RoleGate`
composes by intersection and *"there is no per-route widening in this codebase."* The staff-facing routes
cannot live on `boutique/router.py` (gated `OWNER, SHIFT_MANAGER`) because nothing can widen that gate,
and they cannot live on `staff_router.py` (owner-only) for the same reason.

```python
router = APIRouter(prefix="/manage",
                   dependencies=[Depends(_no_store), Depends(require_role(*StaffRole))])
ELEVATED = Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))
```

`_no_store` is a **sixth local three-line copy** — `auth/staff_router.py:22-27` and `floor/router.py`
both record why. `ELEVATED_ROLES` is spelled locally in `shifts/service.py` as its own two-member
frozenset citing `floor/service.py:101` as the twin, rather than importing `FloorService`'s module to
save two lines. Real HTTP verbs and path parameters; `.claude/rules`' RPC/`@QueryValue` guidance is
Kotlin boilerplate for another codebase (F15 D7 ruled this, `staff_router.py:27-30` restates it).

### D8 — "Not answered" is the ABSENCE of a row

`AvailabilityState(StrEnum)` = `AVAILABLE, UNAVAILABLE, PREFERRED`, pinned by a named DB CHECK because it
is a **stored** value (`SosStatus`' rule; `StaffCardStatus` and `TicketStage` are unpinned because they
are derived).

There is deliberately **no fourth `pending` member**. The roster-readiness read counts missing rows, and
a stored "pending" would make «she has not answered» and «she answered *pending*» indistinguishable in
exactly the query the owner opens this screen to run.

Clearing an answer is a **soft delete** — house rule, no hard delete anywhere in this repo — which returns
the pair to "not answered" by the same predicate.

`preferred` is **advisory input to F40 and never a constraint**: F39 stores it, enforces nothing, and
imposes no cap on how many a staffer may mark. A cap is F40's if it wants one.

### D9 — No retention policy; the registry stays EIGHT

`shift_templates` rows are boutique configuration. `staff_availability` rows carry a staff id, a template
id, a week, one of three enum values and an optional `recorded_by` — **no name, no phone, no free text,
nothing a subject request could name.** They are operational history joined by a `staff_user_id` that is
never nulled, which is precisely the class F38's spec enumerated as retained-and-de-identified, naming
*"F40's future roster rows"* alongside `fitting_room_assignments`, `sos_alerts`, `alteration_tickets` and
`audit_log.actor_id`. The `staff_users` SCRUB blanks the person; these rows survive pointing at an erased
row, and that is the answer rather than a gap.

Growth is not a reason either: 8 staff × 15 shifts × 52 weeks ≈ **6,200 rows/year** per boutique.

`test_the_registry_covers_the_eight_classes_with_the_specified_actions` is a **set equality**, so leaving
it at eight is a positive unchanged assertion and not an omission. F39 touches
`app/privacy/retention.py` not at all.

### D10 — Offboarded staff are never asked

The staff set behind both the submission target and the roster-readiness list is
`deleted_at IS NULL AND (last_day IS NULL OR last_day >= week_end)`, where `week_end = week_start + 6`.

The first clause is the live one — F38's offboarding sets `last_day` and `deleted_at` in one transaction
and `UpdateStaffRequest` cannot set `last_day` alone, so the second clause never fires **today**. It is
written anyway because the day F38's panel gains a "leaving on" field, the silent failure is asking a
staffer for a week she will not work — and F40 then rostering her. A write naming a soft-deleted
`staff_user_id` is a `404`.

### D11 — The write is a whole-week replace for one staffer, in one request

`PUT /manage/shifts/week/availability` with `{week_start, staff_user_id?, entries: [{shift_template_id,
state}]}`. Entries present are upserted; live rows for that (staffer, week) whose template is **not** in
`entries` are soft-deleted. Fifteen taps on a phone become one request, one transaction, one audit row —
and it maps exactly to the screen (mark the list, tap «שמירה»).

Safe against a stale client for `AtelierSettingsUpdate`'s reason: **one writer, one screen, one save**.
`staff_user_id` is optional and defaults to `actor.id`; when present and different, the service applies
the self-or-elevated guard (`floor/service.py:1924`'s exact shape, `NotAuthorizedError` → 403) — the
request names **whom** to record, never **who** is asking, which is the one shape that would turn "any
staffer on herself" into "any staffer on anyone".

Concurrency is the **partial unique index**
`(tenant_id, staff_user_id, shift_template_id, week_start) WHERE deleted_at IS NULL`, not a lock: per
pair, `UPDATE … RETURNING`, and on zero rows `INSERT`, retrying the UPDATE **once** on `IntegrityError`
— `_insert_next_terms_version`'s shipped optimistic shape. No `pg_advisory_xact_lock` — the tenant-wide
key that the booking claim and F28 take is far too coarse for a per-tap write, and the index is a
structural guarantee where that lock is only a serialisation.

A save that changes nothing writes **no audit row** (the shipped no-op rule).

### D12 — Nav: one section, every role, immediately after `atelier`

`SectionKey` gains `"shifts"` — the **seventeenth** member — in `lib/guide.ts` (the union lives there and
`App.tsx` imports it, never the reverse). `GUIDE_STEPS` gains a non-empty tuple, which the
`satisfies Record<SectionKey, readonly [string, ...string[]]>` makes a **type error** to omit.

`App.tsx` gains `const EVERY_ROLE = [...ALL, ...FLOOR_ONLY]` and one NAV row
`{ key: "shifts", labelKey: "nav.shifts", roles: EVERY_ROLE }`, placed **immediately after `atelier`,
before `checkinQr`**. Two constraints force that slot: it must sit **after `floor`** so
`reachable[0]?.key` still lands the three floor roles on «הצוות בקומה», and **before the three owner-only
rows** so the shift manager's prefix stays a contiguous slice.

**This is five coordinated edits, and `Nav.test.tsx` says so in words.** Moving together:
`NAV_LABELS` 15 → **16** (with the new label inserted after «תפירה»), the owner test's name and
assertion (*"all fifteen"* → sixteen), the shift-manager `.slice(0, 12)` → `.slice(0, 13)` in **both**
places it appears, and the seamstress / reception / sales-assistant row-order assertions.

### D13 — The three-state control is native radios, built in the section

A `<fieldset>` per shift with three visually-hidden `<input type="radio">` inside `<label>`s styled as a
segmented group, each label `min-h-11` (44 px). Native radios give arrow-key navigation, a group label and
a correct accessibility tree for free; a `div` grid with `role="radiogroup"` re-implements all three by
hand and is where axe findings come from.

**No new `@boutique/ui` export.** One control on one screen does not earn a package component; the day a
second surface needs it, the extraction is mechanical. `# ponytail: inline segmented radios; promote to
packages/ui when a second consumer appears.`

**`Button size="sm"` (36 px) is forbidden on every control in this feature** — `md` only (F-W1). Note
0032-era finding recorded in LOOP-STATE: `Modal`'s 0.97→1 open animation makes a compliant 44 px control
measure 42.68 px mid-transition; the e2e must settle animations before measuring, not lower the floor.

---

## Data model

**One migration, head + 1 at build time** (observed head `0032`; **F26 holds `0034` in an open worktree**,
so this **will** move — renumber at rebase and re-run `test_exactly_one_migration_head`). Raw-SQL house
style, `0031_dress_reservations.py` copied in every particular: `_STANDARD` block, `_updated_at_trigger`,
`GRANT SELECT, INSERT, UPDATE, DELETE … TO app_user`, `enable_tenant_rls`. No FK constraints, TEXT not
VARCHAR, soft delete via `deleted_at`, `uuid_generate_v4()`, partial indexes, forced RLS — each verified
against 0031 rather than assumed.

```sql
CREATE TABLE shift_templates (
    {_STANDARD},
    day_of_week    INTEGER NOT NULL,      -- 0=Sunday … 6=Saturday, availability_rules' encoding
    label          TEXT    NOT NULL,
    starts_at_time TIME    NOT NULL,
    ends_at_time   TIME    NOT NULL,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT shift_templates_day_check   CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT shift_templates_order_check CHECK (ends_at_time > starts_at_time)
);
CREATE INDEX idx_shift_templates_day
    ON shift_templates (tenant_id, day_of_week, starts_at_time) WHERE deleted_at IS NULL;

CREATE TABLE staff_availability (
    {_STANDARD},
    staff_user_id     UUID NOT NULL,   -- no FK, house rule; validated in the service
    shift_template_id UUID NOT NULL,   -- no FK
    week_start        DATE NOT NULL,   -- the Jerusalem Sunday (D1)
    state             TEXT NOT NULL,
    recorded_by       UUID,            -- NULL when she recorded it herself (D5)
    CONSTRAINT staff_availability_state_check
        CHECK (state IN ('available', 'unavailable', 'preferred')),
    CONSTRAINT staff_availability_week_start_check
        CHECK (EXTRACT(DOW FROM week_start) = 0)
);
CREATE UNIQUE INDEX idx_staff_availability_unique
    ON staff_availability (tenant_id, staff_user_id, shift_template_id, week_start)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_staff_availability_week
    ON staff_availability (tenant_id, week_start, staff_user_id) WHERE deleted_at IS NULL;
```

All CHECKs and both indexes are **named** so `pg_get_constraintdef` has something to pin (0023's rule,
`test_migrations.py`). `downgrade()` drops both tables; **it loses live data** and says so in the header,
0021/0023/0032's convention.

**Models in the SAME commit** — `app/models/shift_template.py`, `app/models/staff_availability.py`, both
`StandardColumns, Base`, and `AvailabilityState` in `models/constants.py`. F38's `0032` shipped
`test_staff_user_declares_every_column_the_hr_migration_adds` and F39 ships its twin for both new tables,
which is the only parity mechanism that exists in `Backend/tests`.

---

## API

`/manage/shifts` — eight routes, five mutating. Second path segment `shifts`, which is a **new** segment
and therefore a `vite.config.ts` proxy-alternation edit (below).

| Route | Gate | Purpose |
|---|---|---|
| `GET /manage/shifts/templates` | every role | live templates, ordered `(day_of_week, sort_order, starts_at_time)` |
| `POST /manage/shifts/templates` | `ELEVATED` | create one → 201 |
| `PATCH /manage/shifts/templates/{template_id}` | `ELEVATED` | full replace of five fields; D4 invalidation |
| `DELETE /manage/shifts/templates/{template_id}` | `ELEVATED` | soft delete + D4 invalidation |
| `POST /manage/shifts/templates/seed` | `ELEVATED` | D3; `409 TEMPLATES_ALREADY_SEEDED`, `409 NO_OPENING_HOURS` |
| `GET /manage/shifts/week` | every role | `?week_start=` optional (default: next week). `{week_start, week_end, deadline_at, locked, templates[], entries[]}` — **her own** entries |
| `PUT /manage/shifts/week/availability` | every role; service self-or-elevated | D11 whole-week replace |
| `GET /manage/shifts/week/submissions` | `ELEVATED` | `?week_start=`; every live staffer × her state per template, `submitted_count`, `total` |

Error codes: `WEEK_OUT_OF_RANGE` (400), `SUBMISSION_CLOSED` (409), `TEMPLATES_ALREADY_SEEDED` (409),
`NO_OPENING_HOURS` (409), `TEMPLATE_LIMIT_REACHED` (400), plus the house 404 for an unknown template or
staffer and 403 for the self-guard.

`deadline_at` is an **ISO-8601 UTC instant** on the wire (`Instant` rule); `week_start` / `week_end` are
plain `datetime.date` (`YYYY-MM-DD`), never instants — `plainDate`'s rule on the FE.

**Audit** — `audit_log.action` is plain TEXT with no CHECK, so no migration:
`SHIFT_TEMPLATE_CREATED` · `SHIFT_TEMPLATE_UPDATED` · `SHIFT_TEMPLATE_DELETED` (the last two carry
`invalidated_submissions`) · `SHIFT_TEMPLATES_SEEDED` (carries the count) · `AVAILABILITY_SUBMITTED`
(carries `week_start`, per-state counts, `on_behalf_of`, `after_deadline`) · `SCHEDULING_SETTINGS_UPDATED`
(D6). **One** `AVAILABILITY_SUBMITTED` rather than one per state: the question this table gets asked is
«who recorded whose availability, when, and was it past the deadline», and each stays one
`WHERE action = …`. `details` carry **ids only, never a display name** — `audit_log` has no retention
class and platform operators read across tenants (`CUSTOMER_UPDATED`'s rule).

---

## Frontend Changes

### Files

| File | Change |
|---|---|
| `Frontend/apps/manage/src/api.ts` | new wire types + 8 calls (below) |
| `Frontend/apps/manage/src/lib/guide.ts` | `SectionKey` + `"shifts"`; `GUIDE_STEPS.shifts` (2 steps) |
| `Frontend/apps/manage/src/App.tsx` | `EVERY_ROLE`, one NAV row after `atelier`, one render branch |
| `Frontend/apps/manage/src/components/ShiftsSection.tsx` | **new** — role-branched container |
| `…/components/MyWeekPanel.tsx` | **new** — every role, her own week |
| `…/components/ShiftTemplatesPane.tsx` | **new** — elevated, the seven-weekday editor + seed |
| `…/components/WeekSubmissionsPane.tsx` | **new** — elevated, roster readiness |
| `…/components/HoursSection.tsx` | one line of copy pointing at the new section (D3's dependency, stated where the owner is) |
| `…/i18n/he.ts` + `…/i18n/ar.ts` | the `shifts.*` + `nav.shifts` + `guide.shifts.*` block, `ar` untranslated |
| `…/validation.ts` | `MAX_TEMPLATES_PER_DAY`, `MAX_SHIFT_LABEL_LENGTH` mirrors (parity-tested) |
| `Frontend/apps/manage/vite.config.ts` | alternation gains `shifts` |
| `Frontend/e2e/fixtures/manage.ts` | route stubs + `settingsPayload()` gains `scheduling` |
| `Frontend/e2e/shifts.spec.ts` | **new** |

### Types

```ts
// NEW
export type AvailabilityState = "available" | "unavailable" | "preferred";

export interface ShiftTemplateInput {
  day_of_week: number;          // 0=Sunday … 6=Saturday
  label: string;
  starts_at_time: string;       // "HH:MM" on the wire, sliced from the server's HH:MM:SS
  ends_at_time: string;
  sort_order: number;
}
export interface ShiftTemplate extends ShiftTemplateInput { id: string }

export interface AvailabilityEntry {
  id: string;
  shift_template_id: string;
  state: AvailabilityState;
  // NULL when she recorded it herself. A name, resolved server-side, so the
  // panel never joins staff rows to render one line.
  recorded_by_name: string | null;
}
export interface ShiftWeek {
  week_start: string;           // "YYYY-MM-DD", a plain Jerusalem calendar date — never a Date
  week_end: string;
  deadline_at: string;          // ISO-8601 UTC instant
  locked: boolean;
  templates: ShiftTemplate[];
  entries: AvailabilityEntry[];
}
export interface WeekSubmissionRow {
  staff_user_id: string;
  display_name: string;
  submitted: boolean;
  entries: { shift_template_id: string; state: AvailabilityState }[];
}
export interface WeekSubmissions {
  week_start: string; submitted_count: number; total: number; rows: WeekSubmissionRow[];
}

// CHANGED — api.ts `Settings`
export interface SchedulingSettings {
  submission_deadline_day_of_week: number;
  submission_deadline_time: string;          // "HH:MM"
}
export interface Settings {
  profile: ProfileSettings;
  toggles: ToggleSettings;
  scheduling: SchedulingSettings;            // ADDED — default-complete on the wire (D6)
}
// CHANGED — UpdateSettingsRequest gains `scheduling?: SchedulingSettings`
//   ⚠ WHOLE-BLOCK, both fields required — `atelier`'s rule, not `toggles`'.
```

### Component behaviour

**`MyWeekPanel`** (every role) — header: «שבוע 8–14 בנובמבר» (`Intl.DateTimeFormat("he-IL")`, day + month,
year appended when it differs from the current one, en-dash, wrapped in `<bdi>` — F28 D6's shipped
formatting rule), then «מועד ההגשה: יום רביעי, 18:00». Below, one `<section>` per weekday that has
templates, each shift a `<fieldset>` with its label, its `HH:MM–HH:MM` and D13's three radios. One
`Button size="md"` «שמירת זמינות» at the bottom, `loading` while in flight, then the shipped
`common.saved` tell. **No polling** — this is a form, and `App.tsx`'s own argument is that a workroom
phone should not run a second loop.

- **Locked week**: a `role="status"` banner, all radios `disabled`, the save button removed (not
  disabled — a disabled save on a locked form is a control that promises an act it cannot perform).
- **A row someone else recorded**: «נרשם על ידי {{name}}.» under the fieldset.
- **Week navigation**: two `Button size="md"` chevrons bounded by D1's ±4 window; disabled at the edges.

**`ShiftTemplatesPane`** (elevated) — the seven weekdays, each a `Card` listing its templates
(label · `HH:MM–HH:MM` · edit · remove) with an «הוספת משמרת» button disabled at
`MAX_TEMPLATES_PER_DAY`. When no template exists anywhere: one `EmptyState` with «יצירת משמרות משעות
הפעילות»; when no `availability_rules` exist either, that button is replaced by a line pointing at
«שעות פעילות». Edit and remove open a `Modal` confirm carrying the D4 invalidation count.

**`WeekSubmissionsPane`** (elevated) — «הגישו 5 מתוך 8» plus a list, submitted rows collapsed to a
`Badge`, not-yet rows first. A row expands to that staffer's states, and each state is tappable — that is
the D5 on-behalf-of write, which reuses the same `PUT` with `staff_user_id`.

### Copy (Hebrew-first; **no exclamation marks**, pre-decided #5, asserted by `i18n.test.ts`)

| Key | Hebrew |
|---|---|
| `nav.shifts` | זמינות למשמרות |
| `shifts.myWeekHeading` | הזמינות שלי |
| `shifts.deadline` | מועד ההגשה: {{day}}, {{time}} |
| `shifts.locked` | מועד ההגשה לשבוע הזה עבר. אפשר לפנות לאחראית המשמרת כדי לעדכן. |
| `shifts.recordedBy` | נרשם על ידי {{name}}. |
| `shifts.noTemplates` | עדיין לא הוגדרו משמרות לשבוע הזה. |
| `shifts.states.available` / `.unavailable` / `.preferred` | זמינה / לא זמינה / מעדיפה |
| `shifts.save` | שמירת זמינות |
| `shifts.templatesHeading` | משמרות הבוטיק |
| `shifts.seed` | יצירת משמרות משעות הפעילות |
| `shifts.seedNoHours` | לא הוגדרו שעות פעילות. אפשר להגדיר אותן במסך שעות פעילות. |
| `shifts.invalidateWarning` | שינוי המשמרת ימחק {{count}} תשובות שכבר נרשמו לשבועות הבאים. |
| `shifts.submittedCount` | הגישו {{submitted}} מתוך {{total}} |
| `shifts.notSubmitted` | טרם הגישה |
| `shifts.errors.closed` | מועד ההגשה לשבוע הזה עבר. |
| `shifts.errors.weekOutOfRange` | אפשר להגיש רק לשבועות הקרובים. |
| `shifts.errors.alreadySeeded` | כבר קיימות משמרות. אפשר לערוך אותן ידנית. |

`ar.ts` gets every key with the approved Hebrew standing in, untranslated (Q3 / pre-decided #47).

### Accessibility floor — a **legal** gate (IS 5568 / WCAG 2.0 AA), not a preference

axe **zero violations** on all three panes and on the locked state. Every touch target ≥ 44 px:
`Button size="md"` only, and D13's radio labels `min-h-11`. Settle the `Modal` open animation before
measuring. RTL throughout; the date range in `<bdi>`. The radio group carries a `<legend>` naming the
shift, so a screen reader announces «חמישי 16:00–21:00, זמינה» rather than three unlabelled radios.

---

## Test strategy

**Fast lane** (no Docker, no Postgres, no Node — `make test` points this lane at a closed port):
- `test_shifts_validation.py` — `week_start` must be a Sunday (all seven weekdays parametrised); the ±4
  window both directions; `ends_at_time > starts_at_time`; per-day and total template caps; label bound;
  `state` membership; deadline day/time shapes.
- **The DST pair, and it is the test this feature most needs**: the resolved deadline instant for a
  January week and a July week from the same `(3, "18:00")` setting must be `16:00Z` and `15:00Z`. A naive
  implementation passes one and fails the other.
- `test_shifts_service.py` — self-or-elevated guard matrix over all five roles × (self, other); the D11
  replace semantics (added / changed / removed / unchanged); the no-op writes no audit row.
- Walkers, all of which **must be updated in this feature's commits**: `test_staff_role_gating.py`
  (`SHIFTS_OPEN` into all three `NON_ELEVATED_REACH` rows; `SHIFTS_ELEVATED` named in the `declared`
  anti-vacuity union and in **nobody's** reach row; nothing enters `OWNER_ONLY` — a shift manager is
  admitted everywhere here), `test_audit_coverage.py` (all five mutating routes must resolve as audited;
  **none** is exempt), `test_cross_tenant_walker.py` (`_MODULE_BY_PREFIX` + `MODULE_WALK_FLOOR["shifts"]`
  + the pinned `(67, 65)` pair), `test_spa_serving.py` (the vite alternation set-equality),
  `test_frontend_constant_parity.py` (the two mirrored caps).
- Frontend (vitest/jsdom) — `ShiftsSection.test.tsx`, `MyWeekPanel.test.tsx` (three-state toggling, save
  payload shape, locked state renders no save button, recorded-by line), `ShiftTemplatesPane.test.tsx`
  (seed empty-state, invalidation confirm count), `WeekSubmissionsPane.test.tsx`, `Nav.test.tsx`
  (D12's five moving numbers), `i18n.test.ts` (every new key resolves, `ar` parity, **zero exclamation
  marks**).

**db-marked** (CI-only — there is no local Docker; note that a `not db` test which dials a real Postgres
is F21's shipped false-green class):
- `test_migrations.py` — both CHECK definitions and both indexes pinned by deparsed literal; up/down
  round-trip; `test_exactly_one_migration_head` **after** the rebase renumber.
- `test_shifts_isolation.py` — RLS on both tables, house suite pattern.
- `test_shifts_db.py` — seed → edit → submit → re-submit lifecycle with its audit rows (details carry no
  display name); the partial unique index makes a re-save idempotent; **two concurrent saves** (NullPool +
  `asyncio.gather`, the F13 precedent) leave exactly one live row per pair; a template edit invalidates
  **future** weeks and leaves the current and past ones alone; a label-only edit invalidates nothing; the
  deadline boundary one second either side on real rows; an elevated write past the deadline succeeds and
  stamps `recorded_by`; a staffer's own does not; an offboarded staffer is absent from the submissions
  list and her id is a 404 on the write; a `week_start` that is not a Sunday is refused **by the DB CHECK**
  even if the service guard is removed.
- `test_boutique_service.py` / `test_tenants_repository.py` — the `scheduling` block merges atomically
  beside a concurrent `toggles` write, and neither clobbers the other.

**s3-marked**: none — this feature touches no storage.

**e2e (Playwright + axe)** — `shifts.spec.ts`: a seamstress signs in, lands on «הצוות בקומה», opens
«זמינות למשמרות», marks a week, saves, sees the tell; an owner seeds templates from opening hours, splits
one, sees the invalidation warning, and reads the submissions pane. **axe zero violations** on each, RTL,
44 px targets measured after animations settle.

---

## Stale-brief traps resolved

1. **Phone + SMS OTP sign-in (brief, twice; and dep `F11`)** — dead since F31; F38 C1 settled it. Session
   cookie, email + password. F11 is a nominal dep this feature does not touch. → **C1**
2. **"Production staff login is externally blocked" (epic risk)** — that risk is about the SMS sender-ID
   registration and reaches F39 only through the OTP flow that no longer exists. F39 has no external
   blocker. → **C1**
3. **"The deadline is a tenant setting"** — *survives*, against the pull of F38's C4. F20's ruling is
   scoped to retention duties the platform enforces; a rota deadline is neither. → **C2**
4. **"After the deadline the week locks for staff; the owner can reopen it"** — the reopen mechanism is
   not built. Elevated actors are simply not subject to the deadline, which needs no state. → **C3**
5. **"pre-filled from opening hours" is under-specified against the real shape** — `availability_rules`
   allows *many* windows per day and carries a slot-engine `capacity`. Resolved: one template per rule
   row, `capacity` dropped, explicit one-time seed that refuses to overwrite. → **D3**
6. **"Saturday has no rules, so it has no templates"** — true, but as an emergent property of the
   tenant's own data. Nothing hardcodes Shabbat, and a boutique that entered Saturday hours gets Saturday
   shifts. → **D3**
7. **F38's O3 premise** — F39 is not the first non-owner screen; `floor` and `atelier` shipped before it.
   O3 stays deferred on its own merits. → **C4**
8. **Retention reflex** — an E8 feature that stores nothing personal. Registry stays at eight, asserted
   by an unchanged set equality. → **C5 / D9**
9. **Migration numbering** — the epic and LOOP-STATE both carry stale head numbers. `main` is `0032`,
   F26 holds `0034` unmerged; resolve from `alembic heads` immediately before the rebase.

---

## Gate 1 questions

**None.** F39 self-approves under Q1. Everything a first draft would have asked was resolvable from
shipped code or a recorded decision, and was resolved rather than escalated:

- *May a shift manager record on another staffer's behalf, or only the owner?* → `ELEVATED_ROLES` is the
  shipped predicate for «may act on anyone» across breaks, room claims and dispatch. **Elevated.** (D5)
- *Is the deadline a tenant setting or an app setting?* → resolved against `config.py`'s own stated
  reasoning and pre-decided #19/#36. **Tenant setting.** (C2/D6)
- *Which week may a staffer submit?* → resolved by the DST argument and `jerusalem.ts`'s existing rule.
  **Explicit server-validated Sunday, future weeks only, ±4-week window.** (D1)
- *Does this need a retention policy?* → resolved against the shipped registry and F38's retained-rows
  enumeration. **No.** (D9)

## Open questions (recorded, non-blocking)

- **O1** `(3, "18:00")` — Wednesday 18:00 — is a guess at the pilot's norm. It is one settings row per
  boutique, so a wrong default costs one dialog, not a migration. Confirm at the pilot.
- **O2** May `preferred` be capped ("at most N per week")? F39 stores it and enforces nothing; **F40**
  decides, and inherits an uncapped column that can express any rule it wants.
- **O3** Overlapping templates on one weekday are legal here (D2). If F40's coverage arithmetic finds
  overlap genuinely ambiguous, the constraint belongs in F40's coverage model, not retroactively here.
- **O4** Copy-forward ("same as last week") is the obvious follow-up and is deliberately not in the first
  cut — the epic lists it as OUT for F40's roster and the same reasoning applies to submissions.
- **O5** F40 will want `is_available(staff_user_id, template_id, week_start)`; every column it needs is
  here and no index change is anticipated. Recorded so F40's spec can confirm rather than discover.
