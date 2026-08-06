# F35 — Staff in-app notification bell

**Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals** (Q1: every feature
that does not touch payments, refunds, privacy-law text or tenant billing self-approves). F35
touches none of them: it stores no customer datum of any kind (§Data model), so it does not reach
F20's territory.

Epic E6, size M. Deps F31, F34 — both merged. Producers F58 (dispatch) and F37 (SOS), both merged.

---

## Conflicts with the brief, recorded and resolved

**C1 — "delivery on F32's existing poll, sharing its version" is unbuildable as written.** F32 was
subsumed into F34 and never built (`LOOP-STATE.md` F32: *status parked, "the board polls the F15
bookings API wholesale; the version field is dropped"*). There is no version field anywhere in the
console. What survives is the **binding intent — the bell never runs a second timer** — and the
shipped code offers a better carrier than F32 would have been. See §Delivery.

**C2 — "F34's dispatch is its first and only producer in this epic; F37's SOS becomes the second"
is stale in both halves.** Dispatch shipped in **F58** (`take_next` / `assign`, PR #40), not F34;
and F37 shipped on 2026-08-03 (PR #41). **Both producers exist on `main` today**, so both are in
scope now and neither is a forward reference.

**C3 — the bell is not on F37's critical path and must not behave as if it were.** `LOOP-STATE.md`
F35: *"DROPPED from F37's deps. SOS ships its own full-screen overlay and its own alerts poll."*
The bell is **the durable record, not the alert channel.** Nothing in F35 may be the only way a
page or a dispatch reaches a person.

---

## IN

- One tenant-scoped `staff_notifications` table, one row per (recipient, event).
- Three producers, each one insert at an existing `_audit.record` call site, in that call's
  transaction: F58 `take_next`, F58 `assign`, F58 `handover`, F37 `raise_sos`.
- Unread count, delivered on the console's existing app-level poll.
- A list read (newest 20) and a mark-read write.
- A bell control in a **new `bell` slot on `ConsoleShell`** (`packages/ui`) + a panel, Hebrew-first
  RTL, `ar` keys untranslated.

## OUT

- **Browser push, APNs/FCM, service workers** — pre-decided #32.
- SMS or email fan-out of in-app notifications; per-staffer preferences; grouping or digesting.
- **The customer bell — that is F24**, a different app, a different substrate, no dependency in
  either direction (F24 is `building` now; F35 must not touch it).
- Terminal SOS states (accept / resolve / cancel) as notifications — see §Producers, declined.
- Deep links from a notification to a specific row; pagination or a cursor; a retention policy.

---

## Data model

Migration `NNNN_staff_notifications.py`. **Number resolved from `alembic heads` at build time**
(observed head on `main` at spec time: `0026_waitlist_entries`; F22 PR #49, F24, F25 and F28 are
ahead in the queue, so the number **will** shift). Renumber at rebase — filename, `revision`,
`down_revision`; `test_exactly_one_migration_head` is the proof. `0022_sos_alerts.py` is the
template for every line below.

```sql
CREATE TABLE staff_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    staff_user_id UUID NOT NULL,          -- THE RECIPIENT. The bell is per staff user.
    actor_staff_user_id UUID NOT NULL,    -- who did it to her. Never equal to staff_user_id.
    kind TEXT NOT NULL,
    entity_id UUID NOT NULL,              -- untyped; `kind` names the table it points into
    read_at TIMESTAMPTZ,
    CONSTRAINT staff_notifications_kind_check
        CHECK (kind IN ('dispatch_assigned', 'room_handed_over', 'sos_targeted'))
);
CREATE INDEX idx_staff_notifications_unread
    ON staff_notifications (tenant_id, staff_user_id)
    WHERE read_at IS NULL AND deleted_at IS NULL;
```
Plus `trg_staff_notifications_updated_at`, `GRANT SELECT, INSERT, UPDATE, DELETE … TO app_user`
(redundant belt-and-braces, house form), and `enable_tenant_rls("staff_notifications")` —
forgetting the last fails `test_tenant_isolation.py`'s scan.

**Decisions.**

- **`kind` is TEXT with a CHECK**, three values, pinned by the DB. House rule: every bounded set is
  pinned (`bookings.status`, `message_log.kind`, `sos_alerts.status`). A fourth kind is a migration
  and therefore a review.
- **Entity reference is an untyped `entity_id` UUID + `kind`**, no FK (no FK constraints exist in
  this schema). `dispatch_assigned` and `room_handed_over` point at `fitting_room_assignments.id`;
  `sos_targeted` at `sos_alerts.id`. It is stored because it is what makes the row a *record*
  rather than a log line — and **it is not emitted on the wire**, because nothing renders it (§API).
  Upgrade path when a deep link exists: one response field, no migration.
- **NO CUSTOMER DATUM, EVER — no name, no phone, no ticket id.** This is the same rule the audit
  block states for `QUEUE_TICKET_DISPATCHED` ("NO NAME AND NO PHONE in `details`, ever") and the
  same defect F58's review caught at r3 (a customer's name in a persistent `role="status"` region).
  The bell says *who did what to you*; the floor screen, under its own audience rules, says *who
  she is*. This is what keeps F35 out of Q1's privacy exception.
- **One index, not two.** The partial index matches the unread count's predicate exactly. The list
  read is `WHERE tenant_id = ? AND staff_user_id = ? AND deleted_at IS NULL ORDER BY created_at
  DESC LIMIT 20` on a table with tens of rows per tenant per day. Upgrade path, with its stated
  cost: `(tenant_id, staff_user_id, created_at DESC) WHERE deleted_at IS NULL`, taking an ACCESS
  EXCLUSIVE lock on a table that will still be small.
- **`deleted_at` has no v1 writer** — nothing soft-deletes a notification; read is a status, not a
  deletion. It is in the predicate because it is on every table in this schema.

**F20's retention registry gets NO row, and that is a decision.** `POLICIES` in
`app/privacy/retention.py` classifies *personal* data; this table holds two staff uuids, an
event uuid and two timestamps — no field a subject request could name. `sos_alerts` carries a
staffer's free text and has no policy either; that is the shipped precedent set one feature ago.
Upgrade path when the pilot's row count says so: one `_purge_staff_notifications` function and one
tuple entry, `created_at < now() - 90 days`. **F38's 7-year staff PII scrub (pre-decided #34) is
unaffected** — it scrubs personal *fields* on `staff_users` while operational history survives by
id, which is exactly the separability F31's risk demanded.

---

## Producers

All four sites are in `Backend/app/floor/service.py`, each one line beside an existing
`_audit.record(...)` call, **inside the same `async with tenant_session(...)` block**, so the
notification commits with the event or not at all. A no-op writes no row — the house rule, and here
it is load-bearing twice over.

| Site | Line (at spec time) | Recipient | `kind` | `entity_id` | Guard |
|---|---|---|---|---|---|
| `take_next` | ~719 | `target_staff_id` | `dispatch_assigned` | `assignment.id` | `!= actor.id` |
| `assign` | ~861 | `target_staff_id` | `dispatch_assigned` | `assignment.id` | `!= actor.id` |
| `handover` | ~1134 | `new_staff_id` | `room_handed_over` | `assignment_id` | `!= actor.id` |
| `raise_sos` | ~1568 | `target_id` | `sos_targeted` | `alert.id` | `target_id is not None` |

**The rule in one sentence: a row is written when somebody else makes you responsible for a
person.** That is why `handover` is in and not a scope creep — it is the same act as `assign` with
the customer already in the room, and a bell that rang for one and not the other would be a bug
nobody could state.

**`take_next` / `assign` self-dispatch writes no row.** Both compute
`target_staff_id = staff_user_id or actor.id`, so a manager taking the next walk-in for herself is
the *ordinary* case, and a notification telling her what she just did is noise on the one surface
whose whole value is that its count means something.

**A role-routed SOS (`target_id is None`) writes NO notification, and this is the sharpest call in
the feature.** `raise_sos` resolves a named target permissively and stores NULL when she is
unreachable; NULL also *means* the shift-manager ROLE, whose audience is `ELEVATED_ROLES` — a role,
not a set of rows. Writing a row per audience member would re-introduce the exact fan-out F37
declined when it did not build `sos_alert_targets`, inside the most latency-sensitive transaction
in the product, to duplicate what `FloorService.sos` already computes at read time for every
elevated caller from t=0. The durable record of a role page is the `SOS_RAISED` audit row.
**Consequence, stated so nobody discovers it: the bell under-reports role-routed pages.** That is
survivable only because C3 holds — the overlay, not the bell, is the emergency channel.

**Declined, with reasons.** `accept_sos` → the raiser ("help is coming"): she is watching the
overlay at a 2-second cadence and the card names the acceptor; the durable answer is the
`SOS_ACCEPTED` audit row. `resolve_sos` / `cancel_sos`: terminal states are news to nobody — the
emergency is over, or she cancelled it herself. `claim` / `release` / `call` / `skip` / `remove`:
none of them hands a person to somebody else. Each is one line at an existing call site if the
pilot asks.

---

## API

**Two routes, both on the existing floor router**, `app/floor/router.py`, second path segment
`floor`. That is deliberate: `vite.config.ts`'s `MANAGE_API` alternation and
`e2e/fixtures/manage.ts`'s `API_FAMILIES` both already carry `floor`, and
`test_spa_serving.py` asserts set-equality between them and the live route table — so an
eighteenth segment would cost two edits and buy nothing while both producers are floor events. The
router-level gate is `require_role(*StaffRole)` (all five), which is exactly the bell's audience, so
`test_staff_role_gating`'s default-deny walker needs no entry.

**The backend module is `app/floor/notifications.py` (repository + reads).
`app/notifications/` IS TAKEN** — it is the SMS/OTP module (`NotificationService`, Twilio, the
`test_notifications_*.py` family). Naming the new work `notifications` at module or test level
collides on both. Test files are `test_bell_*.py`.

**1. Unread count — no route.** Piggybacked on the existing `GET /manage/floor/sos` payload:
`SosResponse` gains `unread_notifications: int`. See §Delivery.

**2. `GET /manage/floor/notifications`** → `{"items": [...]}`, newest first, `LIMIT 20`, hard, no
cursor. Every statement carries **both** predicates, always: RLS scopes the tenant,
`staff_user_id = actor.id` scopes the person. One item:
`{id, kind, actor_name: string|null, created_at, read_at: string|null}`.
`actor_name` is a join to `staff_users.name` with **no `deleted_at` filter** — F37's shipped rule,
so a colleague removed after the fact still has a name; NULL only when her row is gone entirely,
and the copy has a nameless variant for it.

**3. `POST /manage/floor/notifications/read`** — body `{"ids": [uuid, …]}`, max 20, `ForbidExtraModel`.
Marks `read_at = now()` `WHERE staff_user_id = actor.id AND read_at IS NULL` — so nobody can mark
anyone else's, and a re-mark keeps the original timestamp. Returns `{"unread": int}` so the bell
updates without waiting a tick. **One verb, not two**: `ids=[one]` is "she tapped it",
`ids=<the page>` is "mark all". A true mark-all would silently mark rows that arrived after the
list rendered and were never seen, which is the one thing an unread count must not do.
It writes **no audit row** — a person marking her own notification read is not an administrative
act — so it must be added to `UNAUDITED_BY_DECISION` in `test_audit_coverage.py` with that reason.
CSRF is already covered: `CsrfOriginMiddleware` gates on method, not path.

---

## Delivery — the poll decision (resolves C1)

**Verified against shipped code.** `apps/manage/src/lib/sos.tsx`'s `SosProvider` is mounted in
`App.tsx:240`, **wrapping `ConsoleShell`** — so it runs on all 18 nav sections, for all five roles,
at 5s idle / 2s while an alert is live, with `idleStopMs: null` (it never idle-stops). `FloorPanel`
and `BoardSection` each run their own `usePoll`, but they mount on 2 of 18 sections.

**Decision: piggyback `unread_notifications` on the SOS poll's response payload.** Zero new timers,
zero new requests, and it is the only app-wide carrier that exists. The cost is one extra `SELECT
count(*)` on the partial index inside the tick's existing tenant session — the tick already runs ~6
statements, and this one is an index-only scan over tens of rows.

Rejected, with reasons: **a second request on the same timer** doubles the app-wide tick's round
trips to buy independent failure domains that do not matter (if a one-row count fails, the alerts
read failed too). **Fetch-on-page-open**, F24's client bell shape (pre-decided #18's sibling), is
right for a customer who opens a portal and wrong here — a staffer sitting on `customers` for
twenty minutes would learn of a dispatch only by navigating, and the epic's success criterion says
the assignment *lands in her bell*. **A third `usePoll` instance** is refused by the shipped
architecture note in `sos.tsx`: *"three loops on the board screen is this architecture's ceiling."*

Accepted consequence: when the SOS poll reaches a terminal state (401/403), the count freezes. The
console is already dead at that point — `onSessionEnded` drops to the login form — so nothing new
is hidden.

---

## UI contract

**`ConsoleShell` gains one optional prop, `bell?: ReactNode`**, rendered inside the existing
header wrapper `div`, before `{guide}`. The wrapper is why this is a one-line change: the header row
is `justify-between` and the wrapper already groups the chrome controls, so a third child does not
re-spread the row (see the ⚠ comment at `ConsoleShell.tsx:53`). The shell owns the slot and knows
nothing about the control — `guide`'s shipped contract, verbatim. This is a **gate-passed component,
so the design gate is touched**; it is a bell and a modal list assembled from existing components,
so it self-approves under Q2 (designer + `design-critic` must both accept).

`NotificationBell.tsx` in `apps/manage/src/components/`, reading `unreadNotifications` and a
`markRead(ids)` from the extended `SosContextValue`.

- **The control is a plain `<button>` with `min-h-11 min-w-11 px-2`.** Design rule F-W1:
  `Button size="sm"` is 36px and **fails** the 44px touch floor — `ConsoleShell.tsx:60-68` records
  the same defect being fixed on the logout button. Transparent background, so the 44px box is
  invisible and the header stays two controls beside a wordmark.
- **The count is in the accessible name, not in a live region.** `aria-label` is «התראות» with no
  unread and «התראות, {{count}} חדשות» with; the visible badge is `aria-hidden`. **No `role="status"`
  and no `aria-live`** — a 5-second-cadence live region narrating a count is exactly the hostility
  F58's r3 review caught, and SC 4.1.3 is WCAG **2.1**, outside IS 5568 / WCAG 2.0 AA. The badge
  never signals by colour alone: it carries the digit.
- **The panel is `Modal` from `packages/ui`** — native `<dialog>`, so the focus trap, Esc and
  focus-return to the bell are free. ⚠ jsdom has no `<dialog>`; `setup.ts` stubs `showModal()`, so a
  focus assertion that pre-places focus on its own target is vacuous — assert the panel's *content*,
  and leave real focus behaviour to the e2e leg.
- **Rows**: `{actor_name} {verb}` + an **absolute time** (`14:32`), never a relative counter — F37
  forbids live counters on this surface and that is what keeps SC 2.2.2 inapplicable. Unread rows
  are distinguished by weight **and** a text marker, not by colour. Tapping a `dispatch_assigned` or
  `room_handed_over` row marks it read and navigates to `floor`; `sos_targeted` rows are not links
  (the live surface is the overlay, which owns itself). One «סמני הכל כנקרא» button sends the
  rendered page's ids.
- **Copy** (`he.ts`, mirrored untranslated into `ar.ts`), **no exclamation marks**:
  «{{name}} הפנתה אליך לקוחה» · «{{name}} העבירה אליך חדר» · «{{name}} ביקשה עזרה» ·
  nameless fallback «התקבלה התראה» · empty «אין התראות» · title «התראות».

---

## Test plan

**Unit / fast (no DB).**
- `test_bell_service.py` — the four producer guards as a table: self-dispatch writes nothing;
  dispatch-to-another writes exactly one row with the right kind and entity; handover-to-self
  writes nothing; role-routed SOS (`target_id is None`) writes nothing; named SOS writes one.
- `test_bell_validation.py` — `ids` cap of 20, `ForbidExtraModel`, empty list is a no-op 200.
- `test_bell_api.py` — both routes reachable by all five roles; 401 without a session; the list
  never returns another staffer's rows; `POST …/read` with someone else's id changes nothing and
  returns her own count.
- `test_audit_coverage.py` — the exemption entry for `POST …/notifications/read`.
- `test_spa_serving.py` and the `MANAGE_API` alternation must stay **unchanged** — assert it.

**db-marked (real Postgres) — these debut on CI, so run them locally first (F34's play).**
- `test_bell_db.py` — the notification row commits **with** its event and rolls back with it: force
  the `IntegrityError` path in `take_next` and assert zero notification rows alongside zero audit
  rows; assert the CHECK refuses a fourth kind; assert `read_at` is idempotent (second mark keeps
  the first timestamp); assert the unread count's predicate matches the partial index.
- `test_bell_isolation.py` — `test_sos_isolation.py`'s shape: tenant A's staffer never sees tenant
  B's rows through any of the three reads, RLS on and off the session variable.
- `test_migrations.py` — pin the **captured** deparsed CHECK and index predicate, never transcribed
  (Postgres rewrites `IN (…)` to `= ANY (ARRAY[…])` and reorders index predicates).

**Frontend.** `NotificationBell.test.tsx` — count renders in the accessible name; zero unread
renders no badge; mark-read optimistically zeroes and rolls back on rejection. `ConsoleShell`'s
existing tests must pass with a **zero-line diff** when `bell` is omitted (the `guide` extraction's
acceptance gate, reused).

**e2e + axe.** `notifications.spec.ts`, using `fixtures/manage.ts` — the `floor` family is already
intercepted, so this **adds stubs and does not fork the harness**: extend the `/manage/floor/sos`
stub with `unread_notifications`, add stubs for the list and the read POST. Journey: sign in as
`reception` → the bell shows 2 → open the panel → tap a row → it navigates to the floor and the
count drops to 1 → axe **zero violations** on the header with a badge and on the open panel (both
states, 375px and 1440px, RTL). The blocking `Frontend E2E (Playwright + axe)` job is the gate.

---

## Risks

- **The bell under-reports role-routed SOS pages** (§Producers). Owner: team. Mitigated only by C3
  — if anything ever makes the bell an emergency surface, this becomes a defect.
- **The count rides the emergency channel's payload.** A bug in the count query fails the SOS tick.
  Mitigation is that it is one `count(*)` on an exact partial index, tested in the db leg; the
  upgrade path if the pilot ever sees it is the second-request shape, which is a client-side change.
- **The SOS tick grows a statement on every one of 18 sections.** ~6 → ~7 statements per 5s per
  device. At ~10 devices this is under three statements per second per tenant. Measured at the
  pilot, not assumed — same escape hatch and same owner as pre-decided #23.
- **`ConsoleShell` is a gate-passed component shared with no other app today**, but any future
  consumer inherits the new slot. `bell` is optional and omitting it is byte-identical.

## Open questions (none blocking)

- Does the pilot want «help is coming» in the bell (the declined `accept_sos` producer)? One line
  at an existing call site.
- 90-day purge now or at the pilot's first row count? Deferred by decision, not by omission.
